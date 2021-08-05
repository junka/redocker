#!/bin/env python3
import sys
import argparse
from .docker import DockerImage, DockerNetwork
from .docker import DockerContainer
from .docker import Check_id

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version='%(prog)s 0.1.0')
    parser.add_argument('cid', metavar='ID', nargs='+')
    parser.add_argument('--container', action='store_true', dest='con', default=False, help='docker container')
    parser.add_argument('--images', action='store_false', dest='con', default=False, help='docker images')
    ret = parser.parse_args()
    rs = Check_id(ret.cid[0], ret.con)
    if rs == "container":
        reverse_container(ret.cid[0])
    elif rs == "image":
        reverse_image(ret.cid[0])
    elif rs == "network":
        reverse_network(ret.cid[0])
    else:
        print("NOT a valid container nor image ID")
        sys.exit(-1)

def reverse_network(id):
    dn = DockerNetwork(id)
    dn.do_inspect()
    dn.dump()

def reverse_image(id):
    di = DockerImage(id)
    di.do_history()
    di.dump_from_history()

def reverse_container(id):
    dc = DockerContainer(id)
    dc.do_inspect()
    dc.dump()

if __name__ == "__main__":
    main()