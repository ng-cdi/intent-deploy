from compiler.compile import  compile_request
import sys
import backends.OSMDeploy
from manager.intentManager import IntentManager


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

    m = IntentManager()
    m.add_service_orchestrator("127.0.0.1", 9999)
    m.connect()

    resp = m.add_intent(intent)
    print(resp)


    # c = backends.OSMDeploy.OSMDeploy(addr="10.30.64.6")
