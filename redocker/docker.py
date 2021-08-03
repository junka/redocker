import os
import subprocess
import json


def check_output(args, stderr=None):
    '''Run a command and capture its output'''
    return subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=stderr).communicate()[0]

def Check_image_or_container(cid, like) -> int:
    containers = check_output(["docker", "ps", "-q"]).decode().splitlines()
    images = check_output(["docker", "images", "-q"]).decode().splitlines()
    if cid in containers:
        return 0
    if cid in images:
        return 1
    return -1


class DockerContainer:
    """
    """
    def __init__(self, cid) -> None:
        self._id = cid

    def do_inspect(self):
        result = check_output(["docker", "inspect", self._id]).decode()
        self._json = json.loads(result)[0]
        self._image = self._json["Image"].split(':')[1]
        self._networks = self._json["NetworkSettings"]
        self.parse_hostconfig(self._json["HostConfig"])
        self.parse_config(self._json["Config"])
        self.parse_mounts(self._json["Mounts"])

    def parse_hostconfig(self, config):
        self._pidmode = config["PidMode"]
        self._privileged = config["Privileged"]
        self._sec_opt = config["SecurityOpt"]
        self._utsmode = config["UTSMode"]
        self._memory = config["Memory"]
        self._pidsLimit = config["PidsLimit"]
        self._restart_policy = config["RestartPolicy"]["Name"]
        self._restart_rety = config["RestartPolicy"]["MaximumRetryCount"]
        self._networkMode = config["NetworkMode"]
        self._autoremove = config["AutoRemove"]
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
        self._labels = config["Labels"]
        self._workingdir = config["WorkingDir"]
        self._entrypoint = config["Entrypoint"]
        self._tty = config["Tty"]
        self._cmd = config["Cmd"]
        self._stdin = config["AttachStdin"]

    def parse_network(self, net):
        self._port = net["Ports"]

    def dump(self):
        dstr = "docker run "
        if self._pidmode != "":
            dstr += "--pid %s " % self._pidmode
        if self._privileged is True:
            dstr += "--privileged "
        if self._stdin is True:
            dstr += "-i "
        if self._tty is True:
            dstr += "-t "
        if self._autoremove is True:
            dstr += "--rm "
        if self._sec_opt is not None:
            for o in self._sec_opt:
                dstr += "--security-opt %s " % o
        if self._hostname != self._id:
            dstr += "--hostname %s " % self._hostname
        if self._restart_policy != "no":
            dstr += "--restart %s " % self._restart_policy
        for i in self._mounts:
            dstr += "%s " % i
        dstr += self._id
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
