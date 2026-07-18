#!/usr/bin/env python3
"""Compares JSON normalized CLI tool output."""

import argparse
import io
import json
import os
import re
import sys

from datetime import datetime


class CliToolOutputJsonValidator:
    """Compares JSON normalized CLI tool output."""

    _ISO8601_REGEX = re.compile(
        r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)?$"
    )

    def _compare_date_time_value(
        self, reference_value: object, output_value: object
    ) -> dict:
        """Compares 2 values contains a date time value.

        The date time value consist of an ISO 8601 string.

        Args:
          reference_value (object): reference value.
          output_value (object): output value.

        Returns:
          dict[str, str]: comparison result which is an empty dictionary if the values
              match.
        """
        if not self._is_date_time_value(output_value):
            return {
                "issue": "value mismatch",
                "output_value": output_value,
                "reference_value": reference_value,
            }

        try:
            iso8601_string = (
                reference_value[:-1]
                if reference_value.endswith("Z")
                else reference_value
            )
            reference_value_length = len(iso8601_string)

            if reference_value_length == 10:
                _ = datetime.strptime(iso8601_string, "%Y-%m-%d")
            else:
                _ = datetime.strptime(iso8601_string[:19], "%Y-%m-%dT%H:%M:%S")

        except ValueError:
            return {
                "issue": "unable to parse reference value",
                "output_value": output_value,
                "reference_value": reference_value,
            }

        try:
            iso8601_string = (
                output_value[:-1] if output_value.endswith("Z") else output_value
            )
            output_value_length = len(iso8601_string)

            if output_value_length == 10:
                _ = datetime.strptime(iso8601_string, "%Y-%m-%d")
            else:
                _ = datetime.strptime(iso8601_string[:19], "%Y-%m-%dT%H:%M:%S")

        except ValueError:
            return {
                "issue": "unable to parse output value",
                "output_value": output_value,
                "reference_value": reference_value,
            }

        common_prefx = os.path.commonprefix([reference_value, output_value])
        common_prefx_length = len(common_prefx)
        if common_prefx_length < min(reference_value_length, output_value_length):
            return {
                "issue": "value mismatch",
                "output_value": output_value,
                "reference_value": reference_value,
            }

        if reference_value_length != output_value_length:
            return {
                "issue": "value granularity mismatch",
                "output_value": output_value,
                "reference_value": reference_value,
            }

        return {}

    def _is_date_time_value(self, value: object) -> bool:
        """Checks if a value contains a date time value.

        The date time value consist of an ISO 8601 string.

        Args:
          value (object): value.

        Returns:
          bool: True if a date time value, False otherwise.
        """
        if isinstance(value, str):
            return bool(self._ISO8601_REGEX.match(value))

        return False

    def validate(self, reference_file_object: IO, output_file_object: IO) -> dict:
        """Compares JSON normalized CLI tool output.

        Args:
          reference_file_object (file): file-like object containing the reference
              normalized JSON output of CLI tool output.
          output_file_object (file): file-like object containing the normalized JSON
              output of CLI tool output.

        Returns:
          dict[str, str]: validation results.
        """
        file_data = reference_file_object.read()
        reference_dict = json.loads(file_data)

        file_data = output_file_object.read()
        output_dict = json.loads(file_data)

        keys_in_reference = set(reference_dict.keys())
        keys_in_output = set(output_dict.keys())

        additional_keys = list(keys_in_output - keys_in_reference)
        missing_keys = list(keys_in_reference - keys_in_output)

        value_mismatches = {}
        for key in set(keys_in_output).intersection(keys_in_reference):
            output_value = output_dict[key]
            reference_value = reference_dict[key]

            if self._is_date_time_value(reference_value):
                compare_result = self._compare_date_time_value(
                    reference_value, output_value
                )
                if compare_result:
                    value_mismatches[key] = compare_result

            elif output_value != reference_value:
                value_mismatches[key] = {
                    "issue": "value mismatch",
                    "output_value": output_value,
                    "reference_value": reference_value,
                }

        return {
            "additional_attributes": sorted(additional_keys),
            "missing_attributes": sorted(missing_keys),
            "value_mismatches": value_mismatches,
        }


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Compares JSON normalized CLI tool output."
    )
    argument_parser.add_argument(
        "reference_file",
        nargs="?",
        action="store",
        metavar="PATH",
        default=None,
        help="path of the reference file file.",
    )
    options = argument_parser.parse_args()

    if not options.reference_file:
        print("Reference file missing.")
        print("")
        argument_parser.print_help()
        print("")
        sys.exit(1)

    validator = CliToolOutputJsonValidator()

    with open(options.reference_file, encoding="utf-8") as reference_file_object:
        result_dict = validator.validate(reference_file_object, sys.stdin)

    json_string = json.dumps(result_dict, indent=2)
    print(json_string)

    if result_dict["missing_attributes"] or result_dict["value_mismatches"]:
        sys.exit(1)

    sys.exit(0)
