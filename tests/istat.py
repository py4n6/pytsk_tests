"""Tests for the SleuthKit istat output parser."""

import unittest

from sleuthkit import istat

from tests import test_lib


class IstatOutputParserTest(test_lib.BaseTestCase):
    """Tests for the SleuthKit istat output parser."""

    # pylint: disable=protected-access

    # TODO: add tests for _parse_date_time

    def test_parse_file_mode(self):
        """Tests the _parse_file_mode function."""
        parser = istat.IstatOutputParser()

        result = parser._parse_file_mode("brw-rw-r--")
        self.assertEqual(result, 0o60664)

        result = parser._parse_file_mode("crw-rw-rw-")
        self.assertEqual(result, 0o20666)

        result = parser._parse_file_mode("drwxr-xr-x")
        self.assertEqual(result, 0o40755)

        result = parser._parse_file_mode("lrwxrwxrwx")
        self.assertEqual(result, 0o120777)

        result = parser._parse_file_mode("prw-r--r--")
        self.assertEqual(result, 0o10644)

        result = parser._parse_file_mode("rrw-r--r--")
        self.assertEqual(result, 0o100644)

        result = parser._parse_file_mode("srwxrwxrwx")
        self.assertEqual(result, 0o140777)

    def test_parse_section_default(self):
        """Tests the _parse_section_default function."""
        parser = istat.IstatOutputParser()

        result = {}
        parser._parse_section_default("Allocated", result)
        self.assertEqual(result, {"allocated": True})

        result = {}
        parser._parse_section_default("Not Allocated", result)
        self.assertEqual(result, {"allocated": False})

        result = {}
        parser._parse_section_default("uid / gid: 1000 / 1000", result)
        self.assertEqual(result, {"user_identifier": 1000, "group_identifier": 1000})
        result = {}
        parser._parse_section_default("inode: 22", result)
        self.assertEqual(result, {"inode_number": 22})

        result = {}
        parser._parse_section_default("mode: rrw-r--r--", result)
        self.assertEqual(result, {"file_mode": 0o100644})

        with self.assertRaises(RuntimeError):
            result = {}
            parser._parse_section_default("Bogus", result)

    def test_parse_section_inode_times(self):
        """Tests the _parse_section_default function."""
        parser = istat.IstatOutputParser()

        result = {}
        parser._parse_section_inode_times("Accessed: 2020-08-19 18:48:16 (UTC)", result)
        expected_result = {"access_time": "2020-08-19T18:48:16Z"}
        self.assertEqual(result, expected_result)

        result = {}
        parser._parse_section_inode_times(
            "File Modified: 2020-08-19 18:48:16 (UTC)", result
        )
        expected_result = {"modification_time": "2020-08-19T18:48:16Z"}
        self.assertEqual(result, expected_result)

        result = {}
        parser._parse_section_inode_times(
            "Inode Modified: 2020-08-19 18:48:16 (UTC)", result
        )
        expected_result = {"change_time": "2020-08-19T18:48:16Z"}
        self.assertEqual(result, expected_result)

        result = {}
        parser._parse_section_inode_times(
            "File Created: 2020-08-19 18:48:16.123456789 (UTC)", result
        )
        expected_result = {"creation_time": "2020-08-19T18:48:16.123456789Z"}
        self.assertEqual(result, expected_result)

        with self.assertRaises(RuntimeError):
            result = {}
            parser._parse_section_inode_times(
                "Accessed: 2020-08-19 18:48:16 PST", result
            )

        with self.assertRaises(RuntimeError):
            result = {}
            parser._parse_section_inode_times("Bogus", result)

    def test_parse_with_ext2(self):
        """Tests the parse function with ext2 istat output."""
        test_file = self._get_test_file_path(["mke2fs-1.47.0", "istat.ext2.22.txt"])
        self._skip_if_path_not_exists(test_file)

        with open(test_file, encoding="utf-8") as file_object:
            result = istat.IstatOutputParser().parse(file_object)

        expected_result = {
            "access_time": "2026-05-20T17:44:28Z",
            "allocated": True,
            "change_time": "2026-05-20T17:44:28Z",
            "file_mode": 0o100644,
            "group": 0,
            "group_identifier": 0,
            "inode_number": 22,
            "modification_time": "2026-05-20T17:44:28Z",
            "nfs_generation_number": 1803167177,
            "number_of_links": 1,
            "size": 0,
            "user_identifier": 0,
        }
        self.assertEqual(result, expected_result)

    def test_parse_with_ext4(self):
        """Tests the parse function with ext4 istat output."""
        test_file = self._get_test_file_path(["mke2fs-1.47.0", "istat.ext4.22.txt"])
        self._skip_if_path_not_exists(test_file)

        with open(test_file, encoding="utf-8") as file_object:
            result = istat.IstatOutputParser().parse(file_object)

        expected_result = {
            "access_time": "2026-05-20T17:44:31.251573649Z",
            "allocated": True,
            "change_time": "2026-05-20T17:44:31.252573640Z",
            "creation_time": "2026-05-20T17:44:31.251573649Z",
            "file_mode": 0o100644,
            "flags": "Extents,",
            "group": 0,
            "group_identifier": 0,
            "inode_number": 22,
            "modification_time": "2026-05-20T17:44:31.251573649Z",
            "nfs_generation_number": 612045194,
            "number_of_links": 1,
            "size": 0,
            "user_identifier": 0,
        }
        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    unittest.main()
