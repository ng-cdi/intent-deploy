from util.dbMongo import DbMongo
from compiler.compile import compile_yacc
from backends.OSMDeploy import OSMDeploy
import json
import logging
import tempfile
import yaml
import tarfile
from osm_im import validation

from typing import NoReturn, Union, List, Dict


class IntentManager(object):
    """
    docstring
    """

    def __init__(self, addr="127.0.0.1", port: int = 27017, db: str = "intent-state"):
        super().__init__()
        self.config: Dict[str, Union[str, int]] = {
            "host": addr,
            "port": port,
            "name": "intent"
        }
        self.sess: DbMongo = DbMongo(addr, port)
        self.orch: List[OSMDeploy] = []

    def connect(self) -> NoReturn:
        self.sess.db_connect(self.config)

        # this needs better design to support multiple orchestrators
        for orch in self.orch:
            logging.debug("OSM connected")
            # clean existing state
            self.sess.del_list("templates")

            # get a list of installed vnfd
            vnfds = orch.get_vnfd()
            logging.debug("VNFD templated loaded in repo")
            logging.debug(vnfds)
            self.sess.create_list("templates", vnfds)

    def add_intent(self, intent: dict) -> NoReturn:
        resp: dict = compile_yacc(intent)
        logging.info("Inserting new intent ")

        # Store forwarding graph in mongo
        ret = self.sess.create("intentState", resp)

        # initialize the nsd details with some static details.
        intent = resp["policy"]
        intent["name"] = "testIntent"
        # create the nsd state
        nsd = self._create_nsd(intent["name"])

        # Create a vld for the management network
        mgmt_vld = self._create_vld("osm-inet", vim_name="osm-inet", mgmt=True, points=[])

        vnfs = [vnf for vnf in filter(
            lambda vnf: ('vnf' in vnf and vnf['vnf']), resp["policy"]["ffg"])]
        if (len([(vnfs)]) > 0):
            points = [{
                "vnfd-id-ref": vnfs[0]["name"],
                "member-vnf-index-ref": "1",
                "vnfd-connection-point-ref": "input_cp"
            }, {
                "vnfd-id-ref": vnfs[-1]["name"],
                "member-vnf-index-ref": "2",
                "vnfd-connection-point-ref": "output_cp"
            }]

            nsd["vld"].append(self._create_vld("output", points=points))
            nsd["ip-profiles"].append(self._create_ip_profile("output_ip", 0))

        # Get the vnfd for each vnf
        count = 1
        previous_vnf = None
        for vnf in vnfs:
            try:
                self.get_vnfd_template(vnf["name"])
            except:
                logging.error("Failed intent construction: vnfd " +
                              vnf["name"] + " missing")
                return
            if previous_vnf is not None:
                # construct vld names based on vnf names
                name = "%s_%s_dp" % (previous_vnf, vnf["name"])
                points = [{
                    "vnfd-id-ref": previous_vnf,
                    "member-vnf-index-ref": "1",
                    "vnfd-connection-point-ref": "output_cp"
                }, {
                    "vnfd-id-ref": vnf["name"],
                    "member-vnf-index-ref": "2",
                    "vnfd-connection-point-ref": "input_cp"
                }]
                nsd["vld"].append(self._create_vld(name, points=points))

                # define the ip_profile for the previous vnf
                name = "%s_%s_net" % (previous_vnf, vnf["name"])

                nsd["ip-profiles"].append(
                    self._create_ip_profile(name, count-1))
           # Add the vnf to the pool of vnfs for the system.
            nsd["constituent-vnfd"].append({
                "member-vnf-index": count,
                "vnfd-id-ref": vnf["name"]
            })

            # TODO Add the corrent vnf to the mgmt network
            mgmt_vld["vnfd-connection-point-ref"].append({
                "vnfd-id-ref": vnf["name"],
                "member-vnf-index-ref": count,
                "vnfd-connection-point-ref": "mgmt_cp"
            })

            # Update state for next vnf
            count = count + 1
            previous_vnf = vnf["name"]
        # connect the vnfd in the nsd
        # Add the mgmt vld to the main system
        nsd["vld"].append(mgmt_vld)

        nsd = {
            "nsd:nsd-catalog": {
                "nsd": [nsd]
            }
        }
        print(nsd)
        with open("nsd.yaml", 'w') as file:
            yaml.dump(nsd, file)

        print(yaml.dump(nsd))
        validate = validation.Validation()
        validate.pyangbind_validation("nsd", nsd)
        # tmpDir = tempfile.mkdtemp()
        # print(tmpDir)
        # with open(tmpDir+"/nsd.yaml", 'w') as file:
        #     yaml.dump(nsd, file)
        #     # tmpDir.cleanup()
        # tar = tarfile.open("./nsd.tar.gz", 'w')
        # tar.add(tmpDir+"/nsd.yaml", arcname="nsd.yaml")
        # tar.close()
        # print(tmpDir)

        # need to deploy nsd now
        self.orch[0].create_nsd("nsd.yaml")

        # add state details to mongo
        self.sess
        return resp

    def list_intents(self) -> NoReturn:
        return

    def view_intent(self) -> NoReturn:
        return

    def status_intent(self) -> NoReturn:
        return

    def add_service_orchestrator(self, addr: int, port: int) -> NoReturn:
        inst = OSMDeploy()
        inst.connect(addr, port)
        self.orch.append(inst)

    def add_network_orchestrator(self) -> NoReturn:
        return

    def get_vnfd_template(self, name):
        ret = self.sess.get_list(table="templates", q_filter={"id.eq": name})
        logging.debug("get_list(%s) -> %s", name, ret)
        if len(ret) == 0:
            raise KeyError
        return ret

    def _create_vld(self, name: str, vim_name: str = None, points: List = [], mgmt: bool = False) -> Dict[str, str]:
        vld = {
            "id": name,
            "name": name,
            "short-name": name,
            "description": name,
            "version": "1.0",
            "type": "ELAN",
            "mgmt-network": mgmt,
            "vnfd-connection-point-ref": points
        }
        if vim_name is not None:
            vld["vim-network-name"] = vim_name
        return vld

    def _create_nsd(self, name: str) -> Dict[str, str]:
        return {
            "id": name,
            "name": name,
            "short-name": name,
            "description": name,
            "vendor": "NG-CDI, Lancaster University",
            "version": "1.0",
            "constituent-vnfd": [],
            "vld": [],
            "ip-profiles": [],
        }

    def _create_ip_profile(self, name: str, id: int) -> Dict[str, Union[str, Dict[str, str]]]:
        return {
            "name": name,
            "description": name,
            "ip-profile-params": {
                "ip-version": "ipv4",
                "subnet-address": ("192.168.%d.0/24"%(id)),
                "dhcp-params": {
                    "enabled": True,
                    "start-address": ("192.168.%d.4" %(id)),
                }
            }
        }
