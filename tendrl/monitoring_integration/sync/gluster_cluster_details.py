import copy
import etcd


from tendrl.commons.utils import etcd_utils
from tendrl.commons.utils import log_utils as logger
from tendrl.monitoring_integration.grafana import constants
from tendrl.monitoring_integration.grafana import utils

ATTRS = {
    "bricks": ["brick_path", "hostname", "vol_id", "vol_name"],
    "nodes": ["fqdn"],
    "volumes": ["name", "vol_id"]
}


def get_cluster_details(integration_id):
    cluster_details = {}
    try:
        cluster_key = "/clusters/%s" % integration_id
        # Get node details
        cluster_details["hosts"] = get_node_details(cluster_key)
        # Get volume details
        cluster_details["volumes"] = get_volumes_details(cluster_key)
        # Get brick details from subvolumes
        cluster_details["bricks"] = get_brick_details(
            cluster_details["volumes"],
            cluster_key
        )
    except (etcd.EtcdKeyNotFound, KeyError) as ex:
        logger.log(
            "error",
            NS.get("publisher_id", None),
            {'message': str(ex)}
        )
    return cluster_details


def get_node_details(cluster_key):
    node_details = []
    node_list = utils.get_resource_keys(cluster_key, "nodes")
    for node_id in node_list:
        try:
            node = {}
            for attr in ATTRS["nodes"]:
                node[attr] = etcd_utils.read(
                    cluster_key +
                    "/nodes/" +
                    str(node_id) +
                    "/NodeContext/" +
                    attr
                ).value
            node["integration_id"] = cluster_key.split("/")[-1]
            node["sds_name"] = constants.GLUSTER
            node["resource_name"] = str(node["fqdn"]).replace(".", "_")
            node_details.append(node)
        except (KeyError, etcd.EtcdKeyNotFound) as ex:
                logger.log(
                    "error",
                    NS.get("publisher_id", None),
                    {
                        'message': "Error while fetching "
                        "node id {}".format(node_id) + str(ex)
                    }
                )
    return node_details


def get_brick_path(brick_info, cluster_key):
    key = "%s/Bricks/all/%s/brick_path" % (
        cluster_key,
        brick_info.replace(":_", "/")
    )
    path = etcd_utils.read(key).value
    return path.split(":")[1].replace("/", "|")


def get_brick_details(volumes, cluster_key):
    brick_details = []
    for volume in volumes:
        for subvolume in volume["subvolume"]:
            for brick_info in subvolume["bricks"]:
                try:
                    brick = {}
                    brick["hostname"] = brick_info.split(":")[0]
                    brick["vol_id"] = volume["vol_id"]
                    brick["vol_name"] = volume["name"]
                    brick["brick_path"] = get_brick_path(
                        brick_info,
                        cluster_key
                    )
                    brick["sds_name"] = constants.GLUSTER
                    brick["integration_id"] = cluster_key.split("/")[-1]
                    brick["resource_name"] = "%s|%s:%s" % (
                        str(brick["vol_name"]),
                        brick["hostname"],
                        brick["brick_path"].replace("|", "/")
                    )
                    brick_details.append(brick)
                except (KeyError, etcd.EtcdKeyNotFound) as ex:
                    logger.log(
                        "error",
                        NS.get("publisher_id", None),
                        {
                            'message': "Error while brick details for"
                            "brick {}".format(subvolume) + str(ex)
                        }
                    )
    return brick_details


def get_volumes_details(cluster_key):
    volume_details = []
    volume_list = utils.get_resource_keys(cluster_key, "Volumes")
    for volume_id in volume_list:
        deleted = etcd_utils.read(
            cluster_key + "/Volumes/" + str(volume_id) + "/" + "deleted"
        ).value
        if str(deleted).lower() == "false":
            try:
                volume_data = {}
                for attr in ATTRS["volumes"]:
                    volume_data[attr] = etcd_utils.read(
                        cluster_key + "/Volumes/" + str(volume_id) + "/" + attr
                    ).value
                subvolume_key = cluster_key + "/Volumes/" + str(volume_id)
                subvolume_details = get_subvolume_details(subvolume_key)
                volume_data["subvolume"] = subvolume_details
                volume_data["sds_name"] = constants.GLUSTER
                volume_data["integration_id"] = cluster_key.split("/")[-1]
                volume_data["resource_name"] = str(volume_data["name"])
                volume_details.append(volume_data)
            except (KeyError, etcd.EtcdKeyNotFound) as ex:
                logger.log(
                    "error",
                    NS.get("publisher_id", None),
                    {
                        'message': "Error while fetching "
                        "volume id {}".format(volume_id) + str(ex)
                    }
                )
    return volume_details


def get_subvolume_details(key):
    subvolume_brick_details = []
    subvolumes = utils.get_resource_keys(key, "Bricks")
    for subvolume in subvolumes:
        try:
            subvolume_details = {}
            subvolume_details["subvolume"] = ""
            subvolume_details["bricks"] = []
            subvolume_details["subvolume"] = subvolume
            brick_list = utils.get_resource_keys(
                key + "/" + "Bricks", subvolume
            )
            subvolume_details["bricks"] = brick_list
            subvolume_brick_details.append(copy.deepcopy(subvolume_details))
        except (KeyError, etcd.EtcdKeyNotFound) as ex:
            logger.log(
                "error",
                NS.get("publisher_id", None),
                {
                    'message': "Error while fetching "
                    "subvolumes" + str(ex)
                }
            )
    return subvolume_brick_details
