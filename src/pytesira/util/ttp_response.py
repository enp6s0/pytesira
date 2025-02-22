#!/usr/bin/env python3
import re
import logging
from pytesira.util.types import TTPResponseType


class TTPResponse:
    """
    Tesira Text Protocol (TTP) response object

    Handles parsing of the response text with overly complicated regexes... that's pretty much it

    NOTE: this assumes that the TTP channel is set to verbose mode!
    """

    def __init__(self, ttp_string: str) -> None:
        """
        One stop function that does everything this class is supposed to do

        Give it a raw TTP string, and it'll create a response object with all the
        attributes filled in - easy as that!
        """

        # Logger
        self.__logger = logging.getLogger(f"{__name__}")

        # Input string cleaning (and sanity checks)
        ttp_string = str(ttp_string).strip()
        assert ttp_string != "", "empty string given"

        # Save raw string too just in case
        self.raw = ttp_string

        # What's my type (and optionally value?)
        self.type = TTPResponseType.UNKNOWN
        self.value = None
        self.publish_token = None

        # OK response
        if ttp_string.startswith("+OK"):
            # Do I have anything in the response?
            resp = str(ttp_string[3:]).strip()
            if resp == "":
                # Nothing, so we're done here as there's nothing else to process
                self.type = TTPResponseType.CMD_OK
                return
            else:
                # Yes, there's value to be processed
                self.type = TTPResponseType.CMD_OK_VALUE

                # We expect the response to have the format of HEADER_TYPE : VALUE
                # (sometimes the header type is indicative of what the data would look like,
                #  but sometimes it doesn't, so we handle those here)
                header_type = resp.split(":", 1)[0].replace('"', "").strip().lower()
                data = resp.split(":", 1)[1].strip()

                if header_type == "value":

                    # If data is enclosed in double quotes, we strip that
                    if data.startswith('"') and data.endswith('"'):
                        data = data[1:-1]

                    # Parse data
                    self.value = self.__deep_parse_value(data)

                elif header_type == "list":
                    # Extract list items and save (after value conversion of each item) to an attribute
                    items = list(
                        re.findall(
                            '"([^"]*)"', data.split("[", 1)[1].split("]", 1)[0].strip()
                        )
                    )
                    self.value = [self.__value_format(i) for i in items]

        # Error response
        elif ttp_string.startswith("-ERR"):
            self.type = TTPResponseType.CMD_ERROR
            self.value = str(ttp_string[4:]).strip()

        # Subscription response
        elif ttp_string.startswith("!"):

            self.type = TTPResponseType.SUBSCRIPTION

            # Subscription returns are given as a key-value pair, AS PLAIN TEXT, so we need to decode that
            kv_return = self.__deep_parse_value(
                str(ttp_string[1:]), force_first_layer_as_dict=True
            )

            # Now, in kv_return, we have a key-value container. This should have publishToken, which will
            # correspond to the subscription string used to make the subscription, as well as value
            assert (
                "value" in kv_return
            ), f"subscription callback with no data value: {ttp_string}"
            assert (
                "publishToken" in kv_return
            ), f"subscription callback with no publish token: {ttp_string}"

            # Value and publish token data is returned verbatim
            self.value = kv_return["value"]
            self.publish_token = kv_return["publishToken"]

            # We however want to process the publish token a little more too, as it contains valuable
            # data on what it is (format in block.py, should be f"S_{subscribe_type}_{channel_id}_{self._block_id}")
            pub_token_splitted = self.publish_token.split("_", 3)
            assert (
                str(pub_token_splitted[0]).strip() == "S"
            ), f"non-prefixed subscription callback: {ttp_string}"

            self.subscription_type = str(pub_token_splitted[1]).strip()
            self.subscription_channel_id = str(pub_token_splitted[2]).strip()
            self.subscription_block_id = str(pub_token_splitted[3]).strip()

        # Unexpected input
        else:
            raise ValueError(f"invalid TTP response type for input: {ttp_string}")

    def __repr__(self) -> str:
        """
        String representation of TTP responses
        """
        if self.value:
            if self.publish_token and self.type == TTPResponseType.SUBSCRIPTION:
                more_info = f"(type={self.subscription_type},\
                            channel={self.subscription_channel_id},\
                            block={self.subscription_block_id})"
                return f"Subscription response [{type(self.value)}] {self.value} {more_info}"
            else:
                return f"Response [{self.type}][{type(self.value)}] {self.value}"
        else:
            return f"Response [{self.type}]"

    def __deep_parse_value(  # noqa: C901
        self, raw: str, force_first_layer_as_dict: bool = False
    ) -> dict:
        """
        Given a long string (some sort of proto-JSON which doesn't include commas), we want to parse it and return nice
        objects...
        """
        # Clean up raw values
        raw = str(raw).strip()

        # Now, what type do we have here?
        if (raw.startswith("{") and raw.endswith("}")) or force_first_layer_as_dict:
            # Dict
            raw = str(raw[1:-1]) if not force_first_layer_as_dict else raw

            # Find key-value items in here
            key_values = list(
                re.findall(
                    r'("[^"]*"|[^: ]+):\s*("[^"]*"|\[.*?\]|\{.*?\}|[^"\[\{ ]*)', raw
                )
            )

            # Clean up keys and values (strip outermost quotes if one exists)
            cleaned = {}
            for o in key_values:
                key, val = o
                key = str(key).strip()
                val = str(val).strip()

                if key.startswith('"') and key.endswith('"'):
                    key = str(key[1:-1])

                if val.startswith('"') and val.endswith('"'):
                    val = str(val[1:-1])

                # Recursively resolve value items
                # HACK: if key is already in what we're going to return, we ignore
                # repeated keys that comes later. This apparently causes issues in
                # parsing the system error list with two "fault" keys...
                if key not in cleaned:
                    cleaned[key] = self.__deep_parse_value(val)

            return cleaned

        elif raw.startswith("[") and raw.endswith("]"):
            # List
            raw = str(raw[1:-1])

            # Use a stack to parse list for tokens
            tokens = []
            current_token = ""
            stack = []

            for char in raw + " ":
                if char in '["{':
                    stack.append(char)
                    current_token += char
                elif char in ']}"':
                    if stack and (
                        (char == "]" and stack[-1] == "[")
                        or (char == "}" and stack[-1] == "{")
                        or (char == '"' and stack[-1] == '"')
                    ):
                        stack.pop()
                        current_token += char
                    else:
                        current_token += char
                elif char.isspace() and not stack:
                    if current_token:
                        tokens.append(current_token)
                        current_token = ""
                else:
                    current_token += char

            # Add the last token to the list if it's not empty
            if current_token.strip():
                tokens.append(current_token.strip())

            # Recursively process each token
            return [self.__deep_parse_value(t) for t in tokens]

        else:
            # Value (base case)
            if raw.startswith('"') and raw.endswith('"'):
                raw = str(val[1:-1])
            return self.__value_format(raw)

    def __value_format(self, val: float | int | bool | str) -> float | int | bool | str:
        """
        Given a data as a value, try to guess whether it's a string, boolean,
        integer, or float... then cast accordingly
        """
        val = str(val).strip()
        try:
            # Attempt conversion to float
            _ = float(val)

            # If we're here without an error thrown already, we have
            # either a float or bool. We check for existence of a decimal
            # point in the original text to figure out what type:
            if "." in val:
                return float(val)
            else:
                return int(val)
        except ValueError:
            # Can't be converted to floating point number, so it's probably
            # a boolean or string. We do a simple check here:
            if str(val).lower() in ["true", "yes", "on"]:
                return bool(True)
            elif str(val).lower() in ["false", "no", "off"]:
                return bool(False)
            else:
                return str(val)
