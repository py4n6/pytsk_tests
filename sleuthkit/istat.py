#!/usr/bin/env python3
"""Parses Sleuthkit istat output.

To create istat output:
    TZ=UTC istat ext2.raw 22
"""

import fileinput
import json

from typing import Dict
from typing import IO


class IstatOutputParser:
    """Parses Sleuthkit istat output."""

    SECTION_HEADERS = {
        "Direct Blocks:": "direct_blocks",
        "Indirect Blocks:": "indirect_blocks",
        "Inode Times:": "inode_times",
    }

    DEFAULT_ATTRIBUTE_NAMES = {
        "flags": "flags",
        "generation id": "nfs_generation_number",
        "group": "group",
        "inode": "inode_number",
        "mode": "file_mode",
        "num of links": "number_of_links",
        "size": "size",
        "symbolic link to": "link_target",
    }

    INODE_TIMES_ATTRIBUTE_NAMES = {
        "accessed": "access_time",
        "file created": "creation_time",
        "file modified": "modification_time",
        "inode modified": "change_time",
    }

    DATE_TIME_ATTRIBUTES = frozenset(INODE_TIMES_ATTRIBUTE_NAMES.values())

    DECIMAL_ATTRIBUTES = frozenset(
        [
            "group",
            "group_identifier",
            "inode_number",
            "nfs_generation_number",
            "number_of_links",
            "project_identifier",
            "size",
            "user_identifier",
        ]
    )

    FILE_MODE_PERMISSIONS = {
        "-": 0,
        "r": 4,
        "w": 2,
        "x": 1,
    }

    FILE_MODE_TYPES = {
        "b": 0x6000,
        "c": 0x2000,
        "d": 0x4000,
        "l": 0xA000,
        "p": 0x1000,
        "r": 0x8000,
        "s": 0xC000,
    }

    def _parse_date_time(self, value: str) -> str:
        """Converts a istat date and time value to ISO 8601.

        Args:
          value (str): date and time value such as '2020-08-19 18:48:01 (UTC)' or
              '2020-08-19 18:48:20.183375487 (UTC)'.

        Returns:
          str: ISO 8601 formatted date and time value.

        Raises:
          RuntimeError: if the date and time value is not supported.
        """
        if (
            len(value) < 25
            or value[10] != " "
            or value[13] != ":"
            or value[16] != ":"
            or not value.endswith(" (UTC)")
        ):
            raise RuntimeError(f"Unsupported non-UTC time value: {value:s}")

        return f"{value[0:10]:s}T{value[11:-6]:s}Z"

    def _parse_decimal(self, value: str) -> str:
        """Converts a string of a decimal value into an integer.

        Args:
          value (str): decimal value such as '1000'

        Returns:
          int: integer value.

        Raises:
          RuntimeError: if the decimal value is not supported.
        """
        try:
            integer = int(value, 10)
        except ValueError as exception:
            raise RuntimeError("Unable to parse decimal: {value:s}") from exception

        return integer

    def _parse_file_mode(self, file_mode: str) -> int:
        """Converts a file mode string to an octal representation.

        Args:
          file_mode (str): string representation of the file mode, such as 'rrw-r--r--'
              or 'drwxr-xr-x'.

        Returns:
          int: numeric representation of the file mode.
        """
        integer = 0
        for index, character in enumerate(file_mode[-9:]):
            if index in (3, 6):
                integer *= 8

            integer += self.FILE_MODE_PERMISSIONS.get(character)

        return integer + self.FILE_MODE_TYPES.get(file_mode[-10])

    def _parse_section_default(self, line: str, result: Dict[str, str]):
        """Parses a line of the default section.

        Args:
          line (str): line in the section.
          result (dict): resulting attributes.

        Raises:
          RuntimeError: if the line is not supported.
        """
        if line == "Allocated":
            result["allocated"] = True

        elif line == "Not Allocated":
            result["allocated"] = False

        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.lower()

            if key == "uid / gid":
                values = value.strip().split("/")

                result["user_identifier"] = self._parse_decimal(values[0].strip())
                result["group_identifier"] = self._parse_decimal(values[1].strip())
            else:
                attribute_name = self.DEFAULT_ATTRIBUTE_NAMES.get(key)
                attribute_value = value.strip()

                if attribute_name == "file_mode":
                    attribute_value = self._parse_file_mode(attribute_value)
                elif attribute_name in self.DECIMAL_ATTRIBUTES:
                    attribute_value = self._parse_decimal(attribute_value)

                result[attribute_name] = attribute_value

        else:
            raise RuntimeError(f"Unsupported line: {line:s}")

    def _parse_section_inode_times(self, line: str, result: Dict[str, str]):
        """Parses a line of the inode times section.

        Args:
          line (str): line in the section.
          result (dict): resulting attributes.

        Raises:
          RuntimeError: if the line is not supported.
        """
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.lower()

            attribute_name = self.INODE_TIMES_ATTRIBUTE_NAMES.get(key)
            attribute_value = value.strip()

            if attribute_name in self.DATE_TIME_ATTRIBUTES:
                attribute_value = self._parse_date_time(attribute_value)

            result[attribute_name] = attribute_value

        else:
            raise RuntimeError(f"Unsupported line: {line:s}")

    def parse(self, file_object: IO):
        """Parses SleuthKit istat output.

        Args:
          file_object (file): file-like object containing the istat output.

        Returns:
          dict[str, object]: values parsed from the istat output.

        Raises:
          RuntimeError: if the istat output is not supported.
        """
        lines = list(file_object)
        if not lines:
            raise RuntimeError("Missing output")

        result = {}
        section = "default"

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line in self.SECTION_HEADERS:
                section = self.SECTION_HEADERS.get(line)
                continue

            if line.startswith("Extended Attributes"):
                section = "extended_attributes"
                continue

            if section == "default":
                self._parse_section_default(line, result)

            elif section == "direct_blocks":
                # TODO: convert direct block numbers into ranges
                pass

            elif section == "extended_attributes":
                # TODO: parse extended attributes.
                pass

            elif section == "indirect_blocks":
                # TODO: convert indirect block numbers into ranges
                pass

            elif section == "inode_times":
                self._parse_section_inode_times(line, result)

        return result


if __name__ == "__main__":
    parser = IstatOutputParser()
    result_dict = parser.parse(fileinput.input())
    json_string = json.dumps(result_dict, indent=2)
    print(json_string)
