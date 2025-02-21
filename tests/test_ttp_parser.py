#!/usr/bin/env python3
# Tests for the Tesira Text Protocol (TTP) parser
from pytesira.util.ttp_response import TTPResponse, TTPResponseType


def test_parse_ok():
    """
    Test parsing of a basic OK message with no response
    """
    r = TTPResponse("+OK")
    assert r.type == TTPResponseType.CMD_OK


def test_parse_ok_long_spaces():
    """
    Test parsing of a basic OK message with a string that contains longer trailing spaces
    (this should never be the case, but we check for that anyway)
    """
    r = TTPResponse("+OK                                           ")
    assert r.type == TTPResponseType.CMD_OK


def test_parse_ok_simple_value():
    """
    Test parsing of a OK response message where there's also a value, but those values
    are relatively simple - singular values of different types
    """
    vals = [False, 1, -1, 2.0, -2.0, "test string"]
    for v in vals:
        v_str = str(v).lower().strip()
        for vq in [f"{v_str}", f'"{v_str}"']:
            r = TTPResponse(f'+OK "value":{vq}')
            assert r.type == TTPResponseType.CMD_OK_VALUE
            assert r.value == v
            assert type(r.value) is type(v)


def test_parse_subscription_list():
    """
    Test parsing of a subscription value response, where the response value is a list
    """
    # Create test publish token
    TEST_SUBSCRIBE_TYPE = "TestType"
    TEST_CHANNEL_ID = "ALL"
    TEST_BLOCK_ID = "LongName_Block_With_Many_Underscores"

    # f"S_{subscribe_type}_{channel_id}_{self._block_id}")
    TEST_PUBLISH_TOKEN = f"S_{TEST_SUBSCRIBE_TYPE}_{TEST_CHANNEL_ID}_{TEST_BLOCK_ID}"

    for v1 in [True, False, 9.0, -9.0, 1, -1, "stringa"]:
        for v2 in [True, False, 9.0, -9.0, 1, -1, "stringb"]:

            v1_str = str(v1).lower().strip()
            v2_str = str(v2).lower().strip()

            r = TTPResponse(f'! "publishToken":"{TEST_PUBLISH_TOKEN}" "value":[{v1_str} {v2_str}]')
            assert r.type == TTPResponseType.SUBSCRIPTION
            assert r.publish_token == TEST_PUBLISH_TOKEN
            assert r.subscription_type == TEST_SUBSCRIBE_TYPE
            assert r.subscription_channel_id == TEST_CHANNEL_ID
            assert r.subscription_block_id == TEST_BLOCK_ID
            assert type(r.value) is list
            assert len(r.value) == 2

            assert type(r.value[0]) is type(v1)
            assert type(r.value[1]) is type(v2)
            assert r.value[0] == v1
            assert r.value[1] == v2


def test_parse_subscription_singlevalue():
    """
    Test parsing of a subscription value response, where the response value is a singular value
    """
    # Create test publish token
    TEST_SUBSCRIBE_TYPE = "TestType"
    TEST_CHANNEL_ID = "ALL"
    TEST_BLOCK_ID = "BlockName With Spaces"

    # f"S_{subscribe_type}_{channel_id}_{self._block_id}")
    TEST_PUBLISH_TOKEN = f"S_{TEST_SUBSCRIBE_TYPE}_{TEST_CHANNEL_ID}_{TEST_BLOCK_ID}"

    def send_and_check(val_str, expected_val_typed):
        r = TTPResponse(f'! "publishToken":"{TEST_PUBLISH_TOKEN}" "value":{val_str}')
        assert r.type == TTPResponseType.SUBSCRIPTION
        assert r.publish_token == TEST_PUBLISH_TOKEN
        assert r.subscription_type == TEST_SUBSCRIBE_TYPE
        assert r.subscription_channel_id == TEST_CHANNEL_ID
        assert r.subscription_block_id == TEST_BLOCK_ID
        assert type(r.value) is type(expected_val_typed)
        assert r.value == expected_val_typed

    # Check different value types
    for v in [True, False, 0, 1, 2.0, -2.0, "blah"]:

        # We string-encode for sending
        string_encoded = str(v).lower().strip()

        # Now we check the value in different ways: returned directly,
        # or enclosed in double quotes
        send_and_check(string_encoded, v)
        send_and_check(f'"{string_encoded}"', v)


def test_value_formatter():
    """
    Test the value formatter. This is a bit hidden, so we
    bring it out before we do so...

    Note: this is a standalone method and the self paramter
          isn't used, so we just pass None into it
    """
    value_format = lambda v: TTPResponse._TTPResponse__value_format(None, v)  # noqa: E731

    # Boolean
    for v in ["true", "yes", "on"]:
        assert value_format(v) == True  # noqa: E712
    for v in ["false", "no", "off"]:
        assert value_format(v) == False  # noqa: E712

    # Integer
    for i in range(-10, 10):
        assert value_format(f"{i}") == i
        assert type(value_format(f"{i}")) is int

    # Floating-point
    for i in range(-10, 10):
        fv = float(i * 0.1)
        assert value_format(f"{fv}") == fv
        assert type(value_format(f"{fv}")) is float

    # String
    assert value_format("string") == "string"
    assert type(value_format("string")) is str


def test_parse_active_fault_list_nofault():
    """
    Test parsing of active fault list
    """
    RESPONSE = r'+OK "value":[{"id":INDICATOR_NONE_IN_DEVICE "name":"No fault in device" "faults":[] "serialNumber":"00000000"}]'  # noqa: E501
    r = TTPResponse(RESPONSE)
    assert r.type == TTPResponseType.CMD_OK_VALUE

    assert type(r.value) is list
    assert len(r.value) == 1

    rv = r.value[0]
    assert rv["id"] == "INDICATOR_NONE_IN_DEVICE"
    assert rv["name"] == "No fault in device"
    assert rv["faults"] == []
    assert rv["serialNumber"] == 0


def test_parse_active_fault_list_hasfault():
    """
    Test parsing of active fault list when there is a fault reported
    """
    RESPONSE = r'+OK "value":[{"id":INDICATOR_MAJOR_IN_DEVICE "name":"Major Fault in Device" "faults":[{"id":FAULT_DANTE_FLOW_INACTIVE "name":"one or more Dante flows inactive"}] "serialNumber":"11122233"} {"id":INDICATOR_MAJOR_IN_SYSTEM "name":"Major Fault in System" "faults":[] "serialNumber":"11122233"}]'  # noqa: E501
    r = TTPResponse(RESPONSE)
    assert r.type == TTPResponseType.CMD_OK_VALUE

    assert type(r.value) is list
    assert len(r.value) == 1

    rv = r.value[0]
    assert rv["id"] == "INDICATOR_MAJOR_IN_DEVICE"
    assert rv["name"] == "Major Fault in Device"
    assert rv["serialNumber"] == 11122233

    assert type(rv["faults"]) is list
    assert len(rv["faults"]) == 1

    dante_fault = rv["faults"][0]
    assert dante_fault["id"] == "FAULT_DANTE_FLOW_INACTIVE"
    assert dante_fault["name"] == "one or more Dante flows inactive"


def test_parse_network_status():
    """
    Test parsing of a network status response
    """
    RESPONSE = r'+OK "value":{"schemaVersion":2 "hostname":"TestDSP" "defaultGatewayStatus":"0.0.0.0" "networkInterfaceStatusWithName":[{"interfaceId":"control" "networkInterfaceStatus":{"macAddress":"00:00:00:00:00:00" "linkStatus":LINK_1_GB "addressSource":STATIC "ip":"192.168.1.2" "netmask":"255.255.255.0" "dhcpLeaseObtainedDate":"N\/A" "dhcpLeaseExpiresDate":"N\/A" "gateway":"192.168.1.1"}}] "dnsStatus":{"primaryDNSServer":"192.168.1.3" "secondaryDNSServer":"0.0.0.0" "domainName":""} "mDNSEnabled":true "telnetDisabled":true "sshDisabled":false "networkPortMode":PORT_MODE_SEPARATE "rstpEnabled":false "httpsEnabled":false "igmpEnabled":false "switchPortMode":SWITCH_PORT_MODE_CONTROL_AND_MEDIA}'  # noqa: E501

    # Get basic response
    r = TTPResponse(RESPONSE)
    assert r.type == TTPResponseType.CMD_OK_VALUE

    assert r.value["schemaVersion"] == 2
    assert r.value["hostname"] == "TestDSP"
    assert r.value["defaultGatewayStatus"] == "0.0.0.0"

    assert type(r.value["dnsStatus"]) is dict
    assert r.value["dnsStatus"]["domainName"] == ""
    assert r.value["dnsStatus"]["primaryDNSServer"] == "192.168.1.3"
    assert r.value["dnsStatus"]["secondaryDNSServer"] == "0.0.0.0"

    assert r.value["networkPortMode"] == "PORT_MODE_SEPARATE"
    assert r.value["rstpEnabled"] == False  # noqa: E712
    assert r.value["sshDisabled"] == False  # noqa: E712
    assert r.value["telnetDisabled"] == True  # noqa: E712
    assert r.value["switchPortMode"] == "SWITCH_PORT_MODE_CONTROL_AND_MEDIA"

    assert type(r.value["networkInterfaceStatusWithName"]) is list
    assert len(r.value["networkInterfaceStatusWithName"]) == 1

    assert r.value["networkInterfaceStatusWithName"][0]["interfaceId"] == "control"
    assert type(r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]) is dict

    assert r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]["addressSource"] == "STATIC"
    assert r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]["gateway"] == "192.168.1.1"
    assert r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]["ip"] == "192.168.1.2"
    assert r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]["netmask"] == "255.255.255.0"
    assert r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]["macAddress"] == "00:00:00:00:00:00"
    assert r.value["networkInterfaceStatusWithName"][0]["networkInterfaceStatus"]["linkStatus"] == "LINK_1_GB"
