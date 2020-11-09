from util.dbMongo import DbMongo
from compiler.compile import compile_yacc
from backends.OSMDeploy import OSMDeploy
import json
import logging
import tempfile
import yaml
import tarfile
from osm_im import validation


class IntentManager(object):
    """
    docstring
    """
    def __init__(self, addr="127.0.0.1", port=27017, db="intent-state"):
        super().__init__()
        self.config = {
            "host":addr,
            "port": port,
            "name": "intent"
        }
        self.sess = DbMongo(addr, port)
        self.orch = []


    def connect(self):
        self.sess.db_connect(self.config)

        # this needs better design to support multiple orchestrators
        for orch in self.orch:
            logging.debug("OSM connected")
            self.sess.del_list("templates")
            vnfds = orch.get_vnfd()
            logging.debug("VNFD templated loaded in repo")
            logging.debug(vnfds)
            self.sess.create_list("templates", vnfds)

    def add_intent(self, intent):
        resp = compile_yacc(intent)
        logging.info("Inserting new intent ")
        logging.info(resp)
        ret = self.sess.create("intentState", resp)
        resp["policy"]["name"] = "testIntent"
        intent = resp["policy"]
        # create the nsd state
        nsd =  { 
            "id": intent["name"],
            "name": intent["name"], 
            "short-name": intent["name"], 
            "description": intent["name"], 
            "vendor": "NG-CDI, Lancaster University", 
            "version": "1.0", 
            "constituent-vnfd": [], 
            "vld": [], 
            "ip-profiles": [],
        }

        # figure out the source vld
        vld = [
            {
            "id": intent["name"] + "-mgmt",
            "name": intent["name"] + "-mgmt",
            "short-name": intent["name"] + "-mgmt",
            "description": intent["name"] + "managment network",
            "version": "1.0",
            "type": "ELAN",
            "vim-network-name": intent["name"] + "-mgmt",
            "mgmt-network": "true",
            "vnfd-connection-point-ref": []
            #   { "vnfd-id-ref": "aggr",
            #     "member-vnf-index-ref": "1",
            #     "vnfd-connection-point-ref": "aggr_mgmt_cp"
            #     "ip-address": "192.168.28.2"},
          }]

        # Get the vnfd for each vnf
        count = 1
        previous_vld = None
        previous_vnf = None
        for vnf in resp["policy"]["ffg"]:
            if 'vnf' in vnf and vnf['vnf']:

                try:
                    self.get_vnfd_template(vnf["name"])
                except e :
                    logging.error("Failed intent construction: vnfd " + 
                     vnf["name"] + " missing")
                    return

                if previous_vld is not None:
                    previous_vld['id'] = "%s_%s_dp"%(previous_vnf, vnf["name"])
                    previous_vld['name'] = "%s_%s_dp"%(previous_vnf, vnf["name"])
                    previous_vld['short_name'] = "%s_%s_dp"%(previous_vnf, vnf["name"])
                    previous_vld['description'] = "Dataplane link between %s and %s"%(previous_vld, vnf["name"]),
                    previous_vld["vnfd-connection-point-ref"].append({
                        "vnfd-id-ref" : vnf["name"],
                        "member-vnf-index-ref": "2",
                        "vnfd-connection-point-ref": "output_cp"
                    })
                    vnf["vld"].append(previous_vld)
                    nsd["ip-profiles"].append({
                        "name":"%s_%s_net"%(previous_vnf, vnf["name"]),
                    "description": "Subnet between %s and %s"%(previous_vnf, 
                        vnf["name"]),
                    "ip-profile-params": {
                       "ip-version": "ipv4",
                       "subnet-address": "192.168."+str(count-1)+".0/24",
                       "dhcp-params": {
                            "enabled": true,
                            "start-address": "192.168."+str(count-1)+".4",
                        }
                    } 
                })
                nsd["constituent-vnfd"].append({
                    "member-vnf-index" : count,
                    "vnfd-id-ref" : vnf["name"]
                })

                previous_vld = {
                    "version": "1.0",
                    "type": "ELAN",
                    "mgmt-network": False,
                    "vnfd-connection-point-ref": [{
                        "vnf-id-ref": vnf["name"],
                        "member-vnf-index-ref": "1",
                        "vnfd-connection-point-ref": "input_cp"
                    }]
                }
                count = count + 1
                previous_vnf = vnf["name"]

                # connect the vnfd in the nsd
        
        nsd = {
            "nsd:nsd-catalog": {
                "nsd": [nsd]
            }
        }
        print(nsd)
        validate = validation.Validation()
        validate.pyangbind_validation("nsd", nsd)

        tmpDir = tempfile.mkdtemp()
        print(tmpDir)
        with open(tmpDir+"/nsd.yaml", 'w') as file:
            yaml.dump(nsd, file)
            # tmpDir.cleanup()
        tar = tarfile.open("./nsd.tar.gz", 'w')
        tar.add(tmpDir+"/nsd.yaml", arcname="nsd.yaml")
        tar.close()
        print(tmpDir)

        # need to deploy nsd now

        # add state details to mongo
        self.sess
        return resp

    def list_intents(self):
        return

    def view_intent(self):
        return

    def status_intent(self):
        return

    def add_service_orchestrator(self, addr, port):
        inst = OSMDeploy()
        inst.connect(addr, port)
        self.orch.append(inst)

        return

    def add_network_orchestrator(self):
        return

    def get_vnfd_template(self, name):
        ret = self.sess.get_list(table="templates", q_filter={"id.eq":name})
        print(name)
        print(ret)
        if len(ret) == 0:
            raise KeyError
        return ret

