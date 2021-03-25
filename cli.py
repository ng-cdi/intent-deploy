#!/usr/bin/env python3
from compiler.compile import  compile_request
import sys
import backends.OSMDeploy
from manager.intentManager import IntentManager
from binding import ietf_nile
import pyangbind.lib.pybindJSON as pybindJSON



if __name__ == "__main__":
    print("test!")
    if len(sys.argv) < 2:
        print("Not enough arguments!")
        sys.exit(1)
    file = open(sys.argv[1])
    intent = ""
    for line in file.readlines():
        intent = intent + " " + line
    print(intent)

    # nile = ietf_nile()
    # test = nile.nile.intent.add("testIntent")
    # test.middlebox.add("hello")
    # test.middlebox.add("hello2")
    # print(test)
    # print(pybindJSON.dumps(nile))
    # sys.exit(1)
    #
    m = IntentManager()
    m.add_service_orchestrator("127.0.0.1", 9999)
    m.connect()

    resp = m.add_intent(intent)
    print(resp)


    # c = backends.OSMDeploy.OSMDeploy(addr="10.30.64.6")
