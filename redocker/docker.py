import subprocess
import json


def check_output(args, stderr=None):
    '''Run a command and capture its output'''
    return subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=stderr).communicate()[0]

def Check_id(cid, like) -> str:
    containers = check_output(["docker", "ps", "-q"]).decode().splitlines()
    images = check_output(["docker", "images", "-q"]).decode().splitlines()
    nets = check_output(["docker", "network", "ls", "-q"]).decode().splitlines()
    if cid in containers:
        return "container"
    if cid in images:
        return "image"
    if cid in nets:
        return "network"
    return "unknow"

class DockerNetwork:
    """
    docker network
    """
    def __init__(self, nid) -> None:
        self._id = nid

    def do_inspect(self):
        result = check_output(["docker", "inspect", self._id]).decode()
        self._json = json.loads(result)[0]
        self._name = self._json["Name"]
        self._driver = self._json["Driver"]
        self._ipv6 = self._json["EnableIPv6"]
        self._containers = self._json["Containers"]
        self._labels = self._json["Labels"]
        self._internal = self._json["Internal"]
        self._attachable = self._json["Attachable"]
        self._config_only = self._json["ConfigOnly"]
        self._ingress = self._json["Ingress"]
        self.parse_ipam(self._json["IPAM"])

    def parse_ipam(self, ipam):
        cfg = ipam["Config"]
        self.subnet = []
        if cfg is not None:
            for i in cfg:
                self.subnet.append(i["Subnet"])
                
    def dump(self):
        dstr = "docker network create "
        if self._attachable is True:
            dstr += "--attachable "
        if self._config_only is True:
            dstr += "--config-only "
        if self._ingress is True:
            dstr += "--ingress "
        if self._internal is True:
            dstr += "--internal "
        if self._ipv6 is True:
            dstr += "--ipv6"
        dstr += "-d %s " % self._driver
        dstr += self._name
        print(dstr)

class DockerContainer:
    """
    docker container
    """
    def __init__(self, cid) -> None:
        self._id = cid

    def do_inspect(self):
        result = check_output(["docker", "inspect", self._id]).decode()
        self._json = json.loads(result)[0]
        img = DockerImage(self._json["Image"].split(':')[1])
        img.do_inspect()
        self._image = img.get_tags()
        # ignore name on dump
        self._name = self._json["Name"]
        self._name = self._name[self._name.startswith('/') and len('/'):]
        self.parse_network(self._json["NetworkSettings"])
        self.parse_hostconfig(self._json["HostConfig"])
        self.parse_config(self._json["Config"])
        self.parse_mounts(self._json["Mounts"])

    def parse_hostconfig(self, config):
        self._pidmode = config["PidMode"]
        self._privileged = config["Privileged"]
        self._sec_opt = config["SecurityOpt"]
        self._utsmode = config["UTSMode"]
        self._userns = config["UsernsMode"]
        self._publishall = config["PublishAllPorts"]
        self._memory = config["Memory"]
        self._pids_limit = config["PidsLimit"]
        self._ulimits = config["Ulimits"]
        self._restart_policy = config["RestartPolicy"]["Name"]
        self._restart_rety = config["RestartPolicy"]["MaximumRetryCount"]
        self._networkMode = config["NetworkMode"]
        self._autoremove = config["AutoRemove"]
        self._cpuset_cpus = config["CpusetCpus"]
        self._cpuset_mems = config["CpusetMems"]
        self._portbinding = []
        pb = config["PortBindings"]
        if pb is not None:
            for p in pb:
                self._portbinding.append(p)
        self.parse_devices(config["Devices"])

    def parse_mounts(self, mounts):
        self._mounts = []
        for m in mounts:
            if m["Type"] == "volume":
                if m["RW"] is True:
                    self._mounts.append("-v %s:%s" %
                                    (m["Source"],m["Destination"]))
                else:
                    self._mounts.append("-v %s:%s:ro" %
                                    (m["Source"],m["Destination"]))
            elif m["Type"] == "bind":
                if m["RW"] is True:
                    if m["Propagation"] != "" and m["Propagation"]!= "rprivate":
                        self._mounts.append("-v %s:%s,%s" %
                                            (m["Source"],m["Destination"],m["Propagation"]))
                    else:
                        self._mounts.append("-v %s:%s" %
                                            (m["Source"],m["Destination"]))
                else:
                    self._mounts.append("-v %s:%s:ro" %
                                    (m["Source"],m["Destination"]))
            elif m["Type"] == "tmpfs":
                self._mounts.append("--tmpfs %s" % m["Destination"])

    def parse_devices(self, devices):
        self._devices = []
        if devices is not None:
            for d in devices:
                host = d['PathOnHost']
                container = d['PathInContainer']
                perms = d['CgroupPermissions']
                self._devices.append('%s:%s:%s' % (host, container, perms))

    def parse_config(self, config):
        self._hostname = config["Hostname"]
        self._domainname = config["Domainname"]
        self._user = config["User"]
        self._labels = config["Labels"]
        self._workingdir = config["WorkingDir"]
        self._entrypoint = config["Entrypoint"]
        self._tty = config["Tty"]
        self._cmd = config["Cmd"]
        self._stdin = config["OpenStdin"]
        self._attach = config["AttachStdin"]
        self._expose_ports = []
        if len(self._ports) > len(self._portbinding):
            ep = config["ExposedPorts"]
            if ep is not None:
                for p in ep:
                    if p not in self._portbinding:
                        self._expose_ports.append(p)
        self._env = []
        for e in  config["Env"]:
            if e.startswith('DEBIAN_FRONTEND') or \
                e.startswith('TZ=') or \
                e == "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin":                    
                continue
            self._env.append(e)

    def parse_network(self, net):
        self._ports = []
        for p in net["Ports"]:
            self._ports.append(p)
        self._networks = []
        for k in net["Networks"]:
            self._networks.append(k)

    def dump(self):
        dstr = "docker run "
        if self._pidmode != "":
            dstr += "--pid %s " % self._pidmode
        if self._pids_limit is not None:
            dstr += "--pid-limits %d "% self._pids_limit
        if self._privileged is True:
            dstr += "--privileged "
        if self._stdin is True:
            dstr += "-i "
        if self._tty is True:
            dstr += "-t "
        if self._attach is False:
            dstr += "-d "
        if self._autoremove is True:
            dstr += "--rm "
        if self._publishall is True:
            dstr += "-P "
        for p in self._portbinding:
            dstr += "-p %s " % p
        for p in self._expose_ports:
            dstr += "--expose %s " % p
        if self._workingdir != "":
            dstr += "-w %s " % self._workingdir
        if self._user != "":
            dstr += "-u %s " % self._user
        if self._sec_opt is not None:
            for o in self._sec_opt:
                dstr += "--security-opt %s " % o
        for e in self._env:
            dstr += "-e %s " % e
        if self._name is not None:
            dstr += "--name %s " % self._name
        if self._hostname != self._id:
            dstr += "--hostname %s " % self._hostname
        if self._cpuset_cpus is not None:
            dstr += "--cpuset-cpus %s " % self._cpuset_cpus
        if self._cpuset_mems is not None:
            dstr += "--cpuset-mems %s " % self._cpuset_mems
        for i in self._networks:
            dstr += "--net %s "% i
        if self._restart_policy != "no":
            dstr += "--restart %s " % self._restart_policy
        for i in self._mounts:
            dstr += "%s " % i
        dstr += self._image[0]
        if self._cmd is not None:
            for c in self._cmd:
                dstr += " %s" % c
        print(dstr)


class DockerImage:
    """ Docker infos from inspect result
    """
    def __init__(self, cid) -> None:
        self._id = cid
        self._from = None

    def do_inspect(self):
        result = check_output(["docker", "inspect", self._id]).decode()
        self._json = json.loads(result)[0]
        self._id = self._json['Id'].split(':')[1]
        self._repotags = self._json["RepoTags"]
        self._repodigests = self._json["RepoDigests"]
        parent = self._json['Parent']
        if parent != "":
            self._parent = parent.split(':')[1]
        #deprecated 'maintainer'
        self._author = self._json['Author']
        self._config = self._json['Config']
        self._container_config = self._json['ContainerConfig']
        self.parse_layers(self._json['RootFS']["Layers"])
        self.parse_config(self._config)

    def parse_config(self, config):
        self._env = config["Env"]
        self._workingdir = config["WorkingDir"]
        self._entrypoint = config["Entrypoint"]
        self._labels = config["Labels"]
        self._cmd = config["Cmd"]
        self._image = config["Image"]
        self._user = config["User"]

    def parse_layers(self, layers):
        self._layers = []
        # for layer in layers:
        #     print(layer)
        #     self._layers.append(DockerImage(layer.split(':')[1]))

    def get_tags(self):
        return self._repotags

    def do_history(self):
        history = check_output(["docker", "history", "--no-trunc",
                                "--format='{{.ID}}::{{.CreatedBy}}'",
                                self._id]).decode().splitlines()
        self._dockerfile = []
        for i in reversed(history):
            i = i.strip('\'')
            id, cmd = i.split('::')
            # if we got id from history, we can get the first tag
            # to reverse the FROM cmd
            if self._from is None and 'missing' not in id:
                ly_id = DockerImage(id)
                ly_id.do_inspect()
                from_tag = ly_id.get_tags()
                if len(from_tag) > 0:
                    self._dockerfile.clear()
                    self._from = from_tag[0]
                    self._dockerfile.append("FROM %s" % from_tag[0])
                    continue
            start = cmd.find('/bin/sh -c #(nop) ')
            start_run = cmd.find('/bin/sh -c ')
            if start > -1:
                self._dockerfile.append(cmd[start + len('/bin/sh -c #(nop) '):].strip())
            elif start_run > -1:
                self._dockerfile.append("RUN %s" % cmd[start + len('/bin/sh -c '):].strip())
            else:
                self._dockerfile.append("%s" % cmd.strip())

    def dump_inspect(self):
        if self._author != "":
            print("MAINTAINER %s" % self._author)
        for i in self._env:
            print("ENV %s" % i)
        if self._workingdir != "":
            print("WORKDIR %s" % self._workingdir)
        if self._entrypoint is not None:
            print("ENTRYPOINT %s" % self._entrypoint)
        if self._cmd is not None:
            print("CMD %s" % self._cmd)
        if self._user != "":
            print("USER %s" % self._user)
            
    def dump_from_history(self):
        for i in self._dockerfile:
            print(i)
