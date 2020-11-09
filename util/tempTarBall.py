import tempfile
import tarfile
import os
import yaml


class tempTarball(object):
    def __init__(self):
        return


def sample_code():

    desc = {
        "vnfd:vnfd-catalog":
        {
            "vnfd": [
                {"id": "aggr", "name": "aggr", "short-name": "aggr",
                 "connection-point": [
                     {"name": "aggr_mgmt_cp", "type": "VPORT"},
                     {"name": "aggr_prime_cp", "type": "VPORT",
                      "port-security-enabled": False}
                 ],

                    "mgmt-interface": {
                    "cp": "aggr_mgmt_cp"
                 },

                    "vdu": [
                    {"id": "aggr", "name": "aggr", "count": 1, "image": "haproxy_ubuntu", "cloud-init-file": "cloud-init",
                     "vm-flavor": {
                         "vcpu-count": 1, "memory-mb": 4096, "storage-gb": 10
                     },
                        "interface": [
                        {"name": "aggr_mgmt_int", "type": "EXTERNAL",
                         "virtual-interface": {"type": "VIRTIO"},
                         "external-connection-point-ref": "aggr_mgmt_cp",
                         "mgmt-interface": True,
                         "position": "1"},
                         {"name": "aggr_prime_int", "type": "EXTERNAL", "virtual-interface": {"type": "VIRTIO"},
                            "external-connection-point-ref": "aggr_prime_cp", "position": "2"}
                     ]
                     }
                 ]

                 }
            ]
        }
    }

    with open(tmpDir+"/vnfd/vnfd.yaml", 'w') as file:
        yaml.dump(desc, file)
    # tmpDir.cleanup()
    tar = tarfile.open("./vnfd.tar.gz", 'w')
    tar.add(tmpDir+"/vnfd/", arcname="vnfd/")
    tar.close()



if __name__ == "__main__":
    sample_code()
