#!/usr/bin/env python3
"""Compares JSON normalized CLI tool output.

Copied from https://github.com/libyal/yaltests with permission.
"""

import argparse
import ast
import io
import json
import os
import re
import sys

from datetime import datetime

import yaml


class ValidationRule:
    """A validation rule.

    Attributes:
      attributes (list[str]): names of the attributes the rule applies to.
      condition (str): condition when to apply the rule.
      expected_granularity (str): granularity to compare date and time values with,
          such as "seconds".
      expected_value (object): value to expect when the rule applies.
    """

    def __init__(
        self,
        attributes=None,
        condition=None,
        expected_granularity=None,
        expected_value=None,
    ) -> None:
        """Initializes a validation rule.

        Args:
          attributes (Optional[list[str]]): names of the attributes the rule applies to.
          condition (Optional[str]): condition when to apply the rule.
          expected_granularity (Optional[str]): granularity to compare date and time
              values with, such as "seconds".
          expected_value (Optional[object]): value to expect when the rule applies.
        """
        super().__init__()
        self.attributes = attributes or []
        self.condition = condition
        self.expected_granularity = expected_granularity
        self.expected_value = expected_value

    def _evaluate_ast_node(self, node: ast.AST, values: dict) -> Any:
        """Evaluates a node in the condition AST.

        Args:
          node (ast.AST): AST node.
          values (dict[str, object]): attribute values per name.

        Returns:
          bool: True if the AST node matches, False otherwise.

        Raises:
          NameError: if an attribute in the condition is missing from the values.
          ValueError: if the condition contains an unsupported operation.
        """
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id not in values:
                raise NameError(f"undefined attribute: {node.id:s}")

            return values[node.id]

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd):
            left = self._evaluate_ast_node(node.left, values)
            right = self._evaluate_ast_node(node.right, values)
            return left & right

        if isinstance(node, ast.Compare):
            left = self._evaluate_ast_node(node.left, values)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._evaluate_ast_node(comparator, values)

                if isinstance(op, ast.NotEq):
                    if not (left != right):
                        return False

                elif isinstance(op, ast.Eq):
                    if not (left == right):
                        return False

                elif isinstance(op, ast.Lt):
                    if not (left < right):
                        return False

                elif isinstance(op, ast.LtE):
                    if not (left <= right):
                        return False

                elif isinstance(op, ast.Gt):
                    if not (left > right):
                        return False

                elif isinstance(op, ast.GtE):
                    if not (left >= right):
                        return False

            return True

        node_type = type(node)
        raise ValueError(f"unsupported operation: {node_type!s}")

    @classmethod
    def from_dict(cls, values: dict) -> "ValidationRule":
        """Creates a validation rule from values.

        Args:
          values (dict[str, object]): values.

        Returns:
          ValidationRule: a validation rule.
        """
        return cls(
            attributes=values.get("attributes"),
            condition=values.get("condition"),
            expected_granularity=values.get("expected_granularity"),
            expected_value=values.get("expected_value"),
        )

    def matches(self, name: str, values: dict) -> bool:
        """Evaluates a validation rule condition.

        Args:
          name (str): name of the attribute.
          values (dict[str, object]): attribute values per name.

        Returns:
          bool: True if the validation rule applies, False otherwise.
        """
        if name not in self.attributes:
            return False

        if self.condition is None:
            return True

        if not isinstance(self.condition, str):
            return False

        condition_ast = ast.parse(self.condition, mode="eval")

        try:
            result = self._evaluate_ast_node(condition_ast.body, values)
        except (NameError, ValueError) as exception:
            result = False

        return result


class CliToolOutputJsonValidator:
    """Compares JSON normalized CLI tool output."""

    _ISO8601_REGEX = re.compile(
        r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)?$"
    )

    def __init__(self, rules: list) -> None:
        """Initializes a JSON normalized CLI tool output validator.

        Args:
          rules (list[ValidationRule]): validation rules.
        """
        super().__init__()
        self._rules = rules or []

    def _compare_date_time_value(
        self,
        reference_value: object,
        output_value: object,
        expected_granularity: str = None,
    ) -> dict:
        """Compares 2 values contains a date time value.

        The date time value consist of an ISO 8601 string.

        Args:
          reference_value (object): reference value.
          output_value (object): output value.
          expected_granularity (Optional[str]): granularity to compare date and time
              values with, such as "seconds".

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
            if expected_granularity:
                iso8601_string = self._convert_date_time_value(
                    iso8601_string, expected_granularity
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

    def _convert_date_time_value(self, value: str, granularity: str) -> str:
        """Converts a date time value into the specified granularity.

        Args:
          value (str): value, which contains an ISO 8601 string without trailing Z.
          granularity (str): granularity, such as "seconds".

        Returns:
          str: date time value in expected granularity.
        """
        if granularity not in ("seconds",):
            raise RuntimeError(f"Unsupported granularity: {granularity:s}")

        if "." in value:
            value, _ = value.split(".", maxsplit=1)

        return value

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
            reference_value = reference_dict[key]
            output_value = output_dict[key]

            expected_granularity = None
            expected_value = None
            for rule in self._rules:
                if rule.matches(key, output_dict):
                    expected_granularity = rule.expected_granularity
                    expected_value = rule.expected_value
                    break

            if expected_value is None:
                expected_value = reference_value

            if self._is_date_time_value(reference_value):
                compare_result = self._compare_date_time_value(
                    expected_value,
                    output_value,
                    expected_granularity=expected_granularity,
                )
                if compare_result:
                    value_mismatches[key] = compare_result

            elif output_value != expected_value:
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
    # TODO: add option for validation configuration that supports
    # * date and time value granularity mismatch rule

    argument_parser.add_argument(
        "--rules",
        dest="validation_rules",
        action="store",
        metavar="PATH",
        default=None,
        help="path of a YAML file containing validation rules.",
    )
    argument_parser.add_argument(
        "reference_file",
        nargs="?",
        action="store",
        metavar="PATH",
        default=None,
        help="path of the reference file.",
    )
    options = argument_parser.parse_args()

    if not options.reference_file:
        print("Reference file missing.")
        print("")
        argument_parser.print_help()
        print("")
        sys.exit(1)

    validation_rules = []
    if options.validation_rules:
        with open(options.validation_rules, encoding="utf-8") as file_object:
            validation_configuration = yaml.safe_load(file_object) or {}
            validation_rules = [
                ValidationRule.from_dict(rule)
                for rule in validation_configuration.get("rules") or []
            ]

    validator = CliToolOutputJsonValidator(rules=validation_rules)

    with open(options.reference_file, encoding="utf-8") as reference_file_object:
        result_dict = validator.validate(reference_file_object, sys.stdin)

    json_string = json.dumps(result_dict, indent=2)
    print(json_string)

    if result_dict["missing_attributes"] or result_dict["value_mismatches"]:
        sys.exit(1)

    sys.exit(0)
