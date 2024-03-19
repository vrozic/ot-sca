# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Communication interface for OpenTitan OTBN FI framework.

Communication with OpenTitan happens over the uJSON command interface.
"""
import json
import time
from typing import Optional


class OTFIOtbn:
    def __init__(self, target) -> None:
        self.target = target

    def _ujson_otbn_fi_cmd(self) -> None:
        time.sleep(0.01)
        self.target.write(json.dumps("OtbnFi").encode("ascii"))

    def otbn_char_unrolled_reg_op_loop(self) -> None:
        """ Starts the otbn.fi.char.unrolled.reg.op.loop test.
        """
        # OtbnFi command.
        self._ujson_otbn_fi_cmd()
        # CharUnrolledRegOpLoop command.
        time.sleep(0.01)
        self.target.write(json.dumps("CharUnrolledRegOpLoop").encode("ascii"))

    def otbn_char_unrolled_dmem_op_loop(self) -> None:
        """ Starts the otbn.fi.char.unrolled.dmem.op.loop test.
        """
        # OtbnFi command.
        self._ujson_otbn_fi_cmd()
        # CharUnrolledDmemOpLoop command.
        time.sleep(0.01)
        self.target.write(json.dumps("CharUnrolledDmemOpLoop").encode("ascii"))

    def otbn_char_hardware_reg_op_loop(self) -> None:
        """ Starts the otbn.fi.char.hardware.reg.op.loop test.
        """
        # OtbnFi command.
        self._ujson_otbn_fi_cmd()
        # CharHardwareRegOpLoop command.
        time.sleep(0.01)
        self.target.write(json.dumps("CharHardwareRegOpLoop").encode("ascii"))

    def otbn_char_hardware_dmem_op_loop(self) -> None:
        """ Starts the otbn.fi.char.hardware.dmem.op.loop test.
        """
        # OtbnFi command.
        self._ujson_otbn_fi_cmd()
        # CharMemOpLoop command.
        time.sleep(0.01)
        self.target.write(json.dumps("CharHardwareDmemOpLoop").encode("ascii"))

    def init_trigger(self) -> None:
        """ Initialize the FI trigger on the chip.

        Args:
            cfg: Config dict containing the selected test.
        """
        # OtbnFi command.
        self._ujson_otbn_fi_cmd()
        # InitTrigger command.
        time.sleep(0.01)
        self.target.write(json.dumps("InitTrigger").encode("ascii"))

    def start_test(self, cfg: dict) -> None:
        """ Start the selected test.

        Call the function selected in the config file. Uses the getattr()
        construct to call the function.

        Args:
            cfg: Config dict containing the selected test.
        """
        test_function = getattr(self, cfg["test"]["which_test"])
        test_function()

    def read_response(self, max_tries: Optional[int] = 1) -> str:
        """ Read response from Otbn FI framework.
        Args:
            max_tries: Maximum number of attempts to read from UART.

        Returns:
            The JSON response of OpenTitan.
        """
        it = 0
        while it != max_tries:
            read_line = str(self.target.readline())
            if "RESP_OK" in read_line:
                return read_line.split("RESP_OK:")[1].split(" CRC:")[0]
            it += 1
        return ""