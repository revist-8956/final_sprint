"""Static lab invariants; no credentials or AWS API calls. Requires PyYAML."""

from pathlib import Path
import json
import re
import unittest

import yaml


class CfnLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    if tag == "GetAtt" and isinstance(value, str):
        value = value.split(".", 1)
    return {tag if tag == "Ref" else f"Fn::{tag}": value}


CfnLoader.add_multi_constructor("!", intrinsic)
ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return yaml.load((ROOT / name).read_text(), Loader=CfnLoader)


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = load("bootstrap.yaml")
        cls.daily = load("daily-eks.yaml")
        cls.base_resources = cls.bootstrap["Resources"]
        cls.daily_resources = cls.daily["Resources"]

    def test_imports_have_matching_bootstrap_exports(self):
        exports = {
            output["Export"]["Name"]["Fn::Sub"].replace("${AWS::StackName}", "base")
            for output in self.bootstrap["Outputs"].values()
        }
        imports = [
            node["Fn::ImportValue"]["Fn::Sub"].replace("${BootstrapStackName}", "base")
            for node in walk(self.daily)
            if isinstance(node, dict) and "Fn::ImportValue" in node
        ]
        self.assertTrue(imports)
        self.assertTrue(set(imports) <= exports, set(imports) - exports)

    def test_two_explicit_distinct_azs(self):
        for name in ("AvailabilityZoneA", "AvailabilityZoneB"):
            parameter = self.bootstrap["Parameters"][name]
            self.assertEqual(parameter["Type"], "AWS::EC2::AvailabilityZone::Name")
        defaults = [self.bootstrap["Parameters"][name].get("Default") for name in ("AvailabilityZoneA", "AvailabilityZoneB")]
        if all(defaults):
            self.assertNotEqual(*defaults)
        rule = self.bootstrap["Rules"]["DistinctAvailabilityZones"]["Assertions"][0]["Assert"]
        self.assertEqual(rule, {"Fn::Not": [{"Fn::Equals": [{"Ref": "AvailabilityZoneA"}, {"Ref": "AvailabilityZoneB"}]}]})

    def test_network_has_public_and_private_subnets(self):
        subnets = [r for r in self.base_resources.values() if r["Type"] == "AWS::EC2::Subnet"]
        self.assertEqual(len(subnets), 4)
        for suffix in ("A", "B"):
            self.assertTrue(self.base_resources[f"PublicSubnet{suffix}"]["Properties"]["MapPublicIpOnLaunch"])
            self.assertFalse(self.base_resources[f"PrivateSubnet{suffix}"]["Properties"]["MapPublicIpOnLaunch"])

    def test_nat_and_eip_are_daily_not_persistent(self):
        base_types = [r["Type"] for r in self.base_resources.values()]
        self.assertNotIn("AWS::EC2::NatGateway", base_types)
        self.assertNotIn("AWS::EC2::EIP", base_types)
        nat = self.daily_resources["NatGateway"]["Properties"]
        self.assertEqual(nat["AvailabilityMode"], "zonal")
        self.assertEqual(nat["ConnectivityType"], "public")
        self.assertEqual(nat["AllocationId"], {"Fn::GetAtt": ["NatEip", "AllocationId"]})
        self.assertEqual(nat["SubnetId"]["Fn::ImportValue"]["Fn::Sub"], "${BootstrapStackName}-PublicSubnetAId")
        for suffix in ("A", "B"):
            route = self.daily_resources[f"PrivateDefaultRoute{suffix}"]["Properties"]
            self.assertEqual(route["NatGatewayId"], {"Ref": "NatGateway"})
            self.assertEqual(route["RouteTableId"]["Fn::ImportValue"]["Fn::Sub"], f"${{BootstrapStackName}}-PrivateRouteTable{suffix}Id")

    def test_private_nodes_wait_for_nat_routes(self):
        for name in ("ObservabilityNodeGroup", "AppNodeGroup"):
            resource = self.daily_resources[name]
            self.assertEqual(set(resource["DependsOn"]), {"PrivateDefaultRouteA", "PrivateDefaultRouteB"})
            properties = resource["Properties"]
            self.assertEqual(properties["Subnets"], [{"Fn::ImportValue": {"Fn::Sub": "${BootstrapStackName}-PrivateSubnetAId"}}])
            self.assertEqual(properties["ScalingConfig"], {"MinSize": 1, "DesiredSize": 1, "MaxSize": 1})
            self.assertEqual(properties["UpdateConfig"]["UpdateStrategy"], "MINIMAL")
            self.assertNotIn("DiskSize", properties)
            self.assertEqual(properties["CapacityType"], "ON_DEMAND")

    def test_cluster_auth_endpoint_and_standard_support(self):
        cluster = self.daily_resources["Cluster"]["Properties"]
        self.assertEqual(cluster["AccessConfig"]["AuthenticationMode"], "API_AND_CONFIG_MAP")
        self.assertFalse(cluster["AccessConfig"]["BootstrapClusterCreatorAdminPermissions"])
        self.assertEqual(cluster["UpgradePolicy"], {"SupportType": "STANDARD"})
        self.assertEqual(cluster["Version"], {"Ref": "KubernetesVersion"})
        version = self.daily["Parameters"]["KubernetesVersion"]
        if "Default" in version:
            self.assertRegex(str(version["Default"]), version["AllowedPattern"])
        network = cluster["ResourcesVpcConfig"]
        self.assertTrue(network["EndpointPrivateAccess"])
        self.assertEqual(network["PublicAccessCidrs"], [{"Ref": "AdminPublicAccessCidr"}])
        self.assertEqual(network["SubnetIds"], [
            {"Fn::ImportValue": {"Fn::Sub": f"${{BootstrapStackName}}-PrivateSubnet{suffix}Id"}}
            for suffix in ("A", "B")
        ])
        cidr = self.daily["Parameters"]["AdminPublicAccessCidr"]
        if "Default" in cidr:
            self.assertRegex(cidr["Default"], cidr["AllowedPattern"])

    def test_cluster_admin_is_an_explicit_iam_user(self):
        parameters = self.daily["Parameters"]
        user = parameters["ClusterAdminUserArn"]
        if "Default" in user:
            self.assertRegex(user["Default"], user["AllowedPattern"])
        self.assertNotIn("ClusterAdminRoleArn", parameters)
        pattern = user["AllowedPattern"]
        self.assertTrue(re.fullmatch(pattern, "arn:aws:iam::123456789012:user/team/alice"))
        for invalid in (
            "arn:aws:iam::123456789012:root",
            "arn:aws:iam::123456789012:role/admin",
            "arn:aws:sts::123456789012:assumed-role/admin/session",
            "",
        ):
            self.assertIsNone(re.fullmatch(pattern, invalid))
        entry = self.daily_resources["ClusterAdminAccess"]["Properties"]
        self.assertEqual(entry["PrincipalArn"], {"Ref": "ClusterAdminUserArn"})
        self.assertEqual(entry["Type"], "STANDARD")
        self.assertEqual(entry["AccessPolicies"][0]["AccessScope"], {"Type": "cluster"})

    def test_root_and_three_users_have_separate_access_entries(self):
        root = self.daily_resources["RootClusterAdminAccess"]["Properties"]
        self.assertEqual(root["PrincipalArn"], {"Fn::Sub": "arn:${AWS::Partition}:iam::${AWS::AccountId}:root"})
        for resource_name, parameter_name in (
            ("ClusterAdminAccess", "ClusterAdminUserArn"),
            ("ClusterAdminUser2Access", "ClusterAdminUser2Arn"),
            ("ClusterAdminUser3Access", "ClusterAdminUser3Arn"),
        ):
            param = self.daily["Parameters"][parameter_name]
            if "Default" in param:
                self.assertRegex(param["Default"], param["AllowedPattern"])
            self.assertTrue(re.fullmatch(param["AllowedPattern"], "arn:aws:iam::123456789012:user/team/alice"))
            self.assertIsNone(re.fullmatch(param["AllowedPattern"], "arn:aws:iam::123456789012:root"))
            entry = self.daily_resources[resource_name]["Properties"]
            self.assertEqual(entry["PrincipalArn"], {"Ref": parameter_name})
            self.assertEqual(entry["AccessPolicies"][0]["PolicyArn"], root["AccessPolicies"][0]["PolicyArn"])
            self.assertEqual(entry["AccessPolicies"][0]["AccessScope"], {"Type": "cluster"})
        assertions = self.daily["Rules"]["DistinctAdminUsers"]["Assertions"]
        self.assertEqual(len(assertions), 3)

    def test_only_root_disks_in_infrastructure(self):
        for name in ("ObservabilityLaunchTemplate", "AppLaunchTemplate"):
            template = self.daily_resources[name]["Properties"]["LaunchTemplateData"]
            self.assertEqual(len(template["BlockDeviceMappings"]), 1)
            disk = template["BlockDeviceMappings"][0]["Ebs"]
            self.assertTrue(disk["DeleteOnTermination"])
            self.assertTrue(disk["Encrypted"])
            self.assertEqual(disk["VolumeType"], "gp3")
            self.assertEqual(template["MetadataOptions"]["HttpTokens"], "required")
            for forbidden in ("IamInstanceProfile", "SubnetId", "ImageId", "SecurityGroupIds", "UserData"):
                self.assertNotIn(forbidden, template)
        resources = list(self.base_resources.values()) + list(self.daily_resources.values())
        self.assertNotIn("AWS::EC2::Volume", [r["Type"] for r in resources])

    def test_placement_and_cpu_budget(self):
        obs = self.daily_resources["ObservabilityNodeGroup"]["Properties"]
        app = self.daily_resources["AppNodeGroup"]["Properties"]
        self.assertEqual(obs["Labels"], {"workload": "observability"})
        self.assertEqual(obs["Taints"], [{"Key": "dedicated", "Value": "observability", "Effect": "NO_SCHEDULE"}])
        self.assertEqual(app["Labels"], {"workload": "app"})
        self.assertNotIn("Taints", app)
        self.assertEqual(self.daily["Parameters"]["T3CpuCredits"]["Default"], "standard")
        for name in ("ObservabilityLaunchTemplate", "AppLaunchTemplate"):
            credits = self.daily_resources[name]["Properties"]["LaunchTemplateData"]["CreditSpecification"]
            self.assertEqual(credits["Fn::If"][2], {"Ref": "AWS::NoValue"})

    def test_vault_survives_deletion_and_replacement(self):
        vault = self.base_resources["BackupVault"]
        self.assertEqual(vault["DeletionPolicy"], "Retain")
        self.assertEqual(vault["UpdateReplacePolicy"], "Retain")
        self.assertNotIn("BackupVault", self.daily_resources)

    def test_ebs_csi_addon_owns_pod_identity(self):
        csi = self.daily_resources["EbsCsiAddon"]
        self.assertIn("PodIdentityAgentAddon", csi["DependsOn"])
        self.assertEqual(csi["Properties"]["PodIdentityAssociations"][0]["ServiceAccount"], "ebs-csi-controller-sa")
        policies = self.base_resources["EbsCsiRole"]["Properties"]["ManagedPolicyArns"]
        self.assertIn({"Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/AmazonEBSCSIDriverPolicyV2"}, policies)
        standalone = [r["Properties"] for r in self.daily_resources.values()
                      if r["Type"] == "AWS::EKS::PodIdentityAssociation"]
        self.assertNotIn("ebs-csi-controller-sa", [r["ServiceAccount"] for r in standalone])

    def test_karpenter_has_dedicated_node_identity_and_scoped_controller(self):
        profile = self.daily_resources["KarpenterNodeInstanceProfile"]["Properties"]
        self.assertEqual(profile["Roles"], [{"Ref": "KarpenterNodeRole"}])
        self.assertEqual(profile["InstanceProfileName"], {"Fn::Sub": "${ClusterName}-karpenter"})
        access = self.daily_resources["KarpenterNodeAccess"]["Properties"]
        self.assertEqual(access["Type"], "EC2_LINUX")
        self.assertEqual(access["PrincipalArn"], {"Fn::GetAtt": ["KarpenterNodeRole", "Arn"]})
        self.assertNotIn("AccessPolicies", access)
        self.assertNotIn("KubernetesGroups", access)
        association = self.daily_resources["KarpenterPodIdentity"]
        self.assertEqual(association["DependsOn"], "PodIdentityAgentAddon")
        self.assertEqual(association["Properties"]["Namespace"], "karpenter")
        self.assertEqual(association["Properties"]["ServiceAccount"], "karpenter")
        role = self.daily_resources["KarpenterControllerRole"]["Properties"]
        trust = role["AssumeRolePolicyDocument"]["Statement"][0]
        self.assertEqual(trust["Principal"], {"Service": "pods.eks.amazonaws.com"})
        self.assertEqual(set(trust["Action"]), {"sts:AssumeRole", "sts:TagSession"})
        self.assertEqual(trust["Condition"]["StringEquals"]["aws:RequestTag/eks-cluster-name"], {"Ref": "ClusterName"})
        passing = role["Policies"][0]["PolicyDocument"]["Statement"][0]
        self.assertEqual(passing["Action"], "iam:PassRole")
        self.assertEqual(passing["Resource"], access["PrincipalArn"])
        lifecycle = json.loads(self.daily_resources["KarpenterNodeLifecyclePolicy"]["Properties"]["PolicyDocument"]["Fn::Sub"])
        statements = {s["Sid"]: s for s in lifecycle["Statement"]}
        for sid in ("AllowScopedEC2InstanceActionsWithTags", "AllowScopedResourceCreationTagging"):
            self.assertEqual(statements[sid]["Condition"]["StringEquals"]["aws:RequestTag/eks:eks-cluster-name"], "${ClusterName}")
        self.assertEqual(statements["AllowScopedDeletion"]["Condition"]["StringEquals"]["aws:ResourceTag/kubernetes.io/cluster/${ClusterName}"], "owned")
        # Instance profiles belong to CloudFormation, not the controller.
        controller_policy_text = json.dumps(role) + str(self.daily_resources["KarpenterResourceDiscoveryPolicy"])
        for action in ("iam:CreateInstanceProfile", "iam:DeleteInstanceProfile", "iam:AddRoleToInstanceProfile"):
            self.assertNotIn(action, controller_policy_text)

    def test_load_balancer_identity_is_scoped_to_its_service_account(self):
        role = self.daily_resources["LoadBalancerControllerRole"]["Properties"]
        self.assertNotIn("RoleName", role)
        trust = role["AssumeRolePolicyDocument"]["Statement"][0]
        self.assertEqual(trust["Principal"], {"Service": "pods.eks.amazonaws.com"})
        self.assertEqual(set(trust["Action"]), {"sts:AssumeRole", "sts:TagSession"})
        self.assertEqual(trust["Condition"]["StringEquals"], {
            "aws:RequestTag/eks-cluster-name": {"Ref": "ClusterName"},
            "aws:RequestTag/kubernetes-namespace": "kube-system",
            "aws:RequestTag/kubernetes-service-account": "aws-load-balancer-controller",
        })
        association = self.daily_resources["LoadBalancerControllerPodIdentity"]
        self.assertEqual(association["DependsOn"], "PodIdentityAgentAddon")
        self.assertEqual(association["Properties"], {
            "ClusterName": {"Ref": "Cluster"},
            "Namespace": "kube-system",
            "ServiceAccount": "aws-load-balancer-controller",
            "RoleArn": {"Fn::GetAtt": ["LoadBalancerControllerRole", "Arn"]},
        })
        self.assertEqual(role["ManagedPolicyArns"], [{"Ref": "LoadBalancerControllerPolicy"}])

    def test_load_balancer_policy_preserves_upstream_mutation_guards(self):
        policy = json.loads(self.daily_resources["LoadBalancerControllerPolicy"]["Properties"]["PolicyDocument"]["Fn::Sub"])
        statements = policy["Statement"]
        actions = {action for statement in statements for action in statement["Action"]}
        for action in ("elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:DeleteLoadBalancer",
                       "elasticloadbalancing:RegisterTargets", "elasticloadbalancing:ModifyListenerAttributes",
                       "ec2:CreateSecurityGroup", "wafv2:AssociateWebACL"):
            self.assertIn(action, actions)
        self.assertFalse(any("*" in action for action in actions))
        slr = next(s for s in statements if "iam:CreateServiceLinkedRole" in s["Action"])
        self.assertEqual(slr["Condition"]["StringEquals"]["iam:AWSServiceName"], "elasticloadbalancing.amazonaws.com")
        create = next(s for s in statements if "elasticloadbalancing:CreateLoadBalancer" in s["Action"])
        delete = next(s for s in statements if "elasticloadbalancing:DeleteLoadBalancer" in s["Action"])
        self.assertEqual(create["Condition"]["Null"]["aws:RequestTag/elbv2.k8s.aws/cluster"], "false")
        self.assertEqual(delete["Condition"]["Null"]["aws:ResourceTag/elbv2.k8s.aws/cluster"], "false")

    def test_no_backup_or_restore_magic_custom_resources(self):
        resources = list(self.base_resources.values()) + list(self.daily_resources.values())
        for resource in resources:
            self.assertFalse(resource["Type"].startswith("Custom::"))
            self.assertNotEqual(resource["Type"], "AWS::Lambda::Function")


if __name__ == "__main__":
    unittest.main()
