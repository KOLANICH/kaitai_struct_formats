#!/usr/bin/env python3

import heapq
import io
import mmap
import os
import struct
import sys
import typing
from enum import IntEnum, IntFlag
from itertools import takewhile
from pathlib import Path
from zlib import crc32

from plumbum import cli


class uint(int):
	def __init__(self, v):
		self = v


class uint64_t(uint):
	def __init__(self, v):
		super().__init__(v & 0xFFFFFFFFFFFFFFFF)


class uint32_t(uint64_t):
	def __init__(self, v):
		super().__init__(v & 0xFFFFFFFF)


class uint16_t(uint32_t):
	def __init__(self, v):
		super().__init__(v & 0xFFFF)


class uint8_t(uint16_t):
	def __init__(self, v):
		super().__init__(v & 0xFF)


class int64_t(int):
	def __init__(self, v):
		super().__init__(v & 0xFFFFFFFFFFFFFFFF)


class size_t(uint64_t):
	pass


class int32_t(int64_t):
	def __init__(self, v):
		super().__init__(v & 0xFFFFFFFF)


class int16_t(int32_t):
	def __init__(self, v):
		super().__init__(v & 0xFFFF)


class int8_t(int16_t):
	def __init__(self, v):
		super().__init__(v & 0xFF)


# there probably aren't any displays with more waveforms than this (we hope)
# (technically the header allows for 256 * 256 waveforms but that's not realistic)
MAX_WAVEFORMS = 4096

# these are the actual maximums
MAX_MODES = 256
MAX_TEMP_RANGES = 256

# for unknown reasons addresses in the .wrf file
# need to be offset by 63 bytes
MYSTERIOUS_OFFSET = 63


class MODE(IntEnum):
	INIT = 0x0
	DU = 0x1
	GC16 = 0x2
	# GC4 = WAVEFORM_MODE_GC16
	GC16_FAST = 0x3
	A2 = 0x4
	GL16 = 0x5
	GL16_FAST = 0x6
	DU4 = 0x7
	REAGL = 0x8
	REAGLD = 0x9
	GL4 = 0xA
	GL16_INV = 0xB


update_modes = {MODE.INIT: "INIT (panel initialization / clear screen to white)", MODE.DU: "DU (direct update, gray to black/white transition, 1bpp)", MODE.GC16: "GC16 (high fidelity, flashing, 4bpp)", MODE.GC16_FAST: "GC16_FAST (medium fidelity, 4bpp)", MODE.A2: "A2 (animation update, fastest and lowest fidelity)", MODE.GL16: "GL16 (high fidelity from white transition, 4bpp)", MODE.GL16_FAST: "GL16_FAST (medium fidelity from white transition, 4bpp)", MODE.DU4: "DU4 (direct update, medium fidelity, text to text, 2bpp)", MODE.REAGL: "REAGL (non-flashing, ghost-compensation)", MODE.REAGLD: "REAGLD (non-flashing, ghost-compensation with dithering)", MODE.GL4: "GL4 (2-bit from white transition, 2bpp)", MODE.GL16_INV: "GL16_INV (high fidelity for black transition, 4bpp)", 0x00: None}

mfg_codes = {0x33: 'ED060SCF (V220 6" Tequila)', 0x34: "ED060SCFH1 (V220 Tequila Hydis – Line 2)", 0x35: "ED060SCFH1 (V220 Tequila Hydis – Line 3)", 0x36: "ED060SCFC1 (V220 Tequila CMO)", 0x37: "ED060SCFT1 (V220 Tequila CPT)", 0x38: "ED060SCG (V220 Whitney)", 0x39: "ED060SCGH1 (V220 Whitney Hydis – Line 2)", 0x3A: "ED060SCGH1 (V220 Whitney Hydis – Line 3)", 0x3B: "ED060SCGC1 (V220 Whitney CMO)", 0x3C: "ED060SCGT1 (V220 Whitney CPT)", 0xA0: "Unknown LGD panel", 0xA1: "Unknown LGD panel", 0xA2: "Unknown LGD panel", 0xA3: "LB060S03-RD02 (LGD Tequila Line 1)", 0xA4: "2nd LGD Tequila Line", 0xA5: "LB060S05-RD02 (LGD Whitney Line 1)", 0xA6: "2nd LGD Whitney Line", 0xA7: "Unknown LGD panel", 0xA8: "Unknown LGD panel", 0x00: None}

run_types = {0x00: "[B]aseline", 0x01: "[T]est/trial", 0x02: "[P]roduction", 0x03: "[Q]ualification", 0x04: "V110[A]", 0x05: "V220[C]", 0x06: "D", 0x07: "V220[E]", 0x08: "F", 0x09: "G", 0x0A: "H", 0x0B: "I", 0x0C: "J", 0x0D: "K", 0x0E: "L", 0x0F: "M", 0x10: "N", 0x00: None}

fpl_platforms = {0x00: "2.0", 0x01: "2.1", 0x02: "2.3", 0x03: "V110", 0x04: "V110A", 0x06: "V220", 0x07: "V250", 0x08: "V220E", 0x00: None}

fpl_sizes = {0x32: '5", unknown resolution', 0x3C: '6", 800x600', 0x3D: '6.1", 1024x768', 0x3F: '6", 800x600', 0x50: '8", unknown resolution', 0x61: '9.7", 1200x825', 0x63: '9.7", 1600x1200', 0x00: None}

fpl_rates = {0x50: "50Hz", 0x60: "60Hz", 0x85: "85Hz", 0x00: None}

mode_versions = {0x00: "MU/GU/GC/PU (V100 modes)", 0x01: "DU/GC16/GC4 (V110/V110A modes)", 0x02: "DU/GC16/GC4 (V110/V110A modes)", 0x03: "DU/GC16/GC4/AU (V220, 50Hz/85Hz modes)", 0x04: "DU/GC16/AU (V220, 85Hz modes)", 0x06: "? (V220: 210 dpi: 85Hz modes)", 0x07: "? (V220, 210 dpi, 85Hz modes)", 0x00: None}


waveform_types = {0x0B: "TE", 0x0E: "WE", 0x15: "WJ", 0x16: "WK", 0x17: "WL", 0x18: "VJ", 0x2B: "WR", 0x3C: "AA", 0x4B: "AC", 0x4C: "BD", 0x50: "AE", 0x00: None}


waveform_tuning_biases = {0x00: "Standard", 0x01: "Increased DS Blooming V110/V110E", 0x02: "Increased DS Blooming V220/V220E", 0x00: None}


def get_desc(table, key: int, default) -> str:
	if key in table:
		return table[key]
	else:
		if default:
			return default
		else:
			return "Unknown"


def print_modes(mode_count: uint8_t) -> None:
	i: uint8_t = 0
	desc: str = ""

	print("Modes in file:")
	for i in range(0, mode_count):
		desc = get_desc(update_modes, i, "Unknown mode")
		print("	{:2d}: {}".format(i, desc))

	print("")


def get_desc_mfg_code(mfg_code: uint) -> str:
	desc: str = get_desc(mfg_codes, mfg_code, None)

	if desc:
		return desc

	if mfg_code >= 0x33 and mfg_code < 0x3C:
		return "PVI/EIH panel\0"
	elif mfg_code >= 0xA0 and mfg_code < 0xA8:
		return "LGD panel\0"

	return "Unknown code\0"


class waveform_data_header:
	"""
    struct waveform_data_header {
            uint32_t checksum; # 0
            uint32_t filesize; # 4
            uint32_t serial; # 8 serial number
            uint8_t run_type; # 12
            uint8_t fpl_platform; # 13
            uint16_t fpl_lot; # 14
            uint8_t mode_version_or_adhesive_run_num; # 16
            uint8_t waveform_version; # 17
            uint8_t waveform_subversion; # 18
            uint8_t waveform_type; # 19
            uint8_t fpl_size; # 20 (aka panel_size)
            uint8_t mfg_code; # 21 (aka amepd_part_number)
            uint8_t waveform_tuning_bias_or_rev; # 22
            uint8_t fpl_rate; # 23 (aka frame_rate)
            uint8_t unknown0; # 24
            uint8_t vcom_shifted; # 25
            uint16_t unknown1; # 26
            uint16_t xwia_LO; # 28 # address of extra waveform information
            uint8_t xwia_HI; # 30 address of extra waveform information
            uint8_t cs1; # 31 checksum 1
            uint16_t wmta_LO # 32;
            uint8_t wmta_HI # 34;
            uint8_t fvsn;
            uint8_t luts;
            uint8_t mc; # mode count (length of mode table - 1)
            uint8_t trc; # temperature range count (length of temperature table - 1)
            uint8_t advanced_wfm_flags;
            uint8_t eb;
            uint8_t sb;
            uint8_t reserved0_1;
            uint8_t reserved0_2;
            uint8_t reserved0_3;
            uint8_t reserved0_4;
            uint8_t reserved0_5;
            uint8_t cs2; # checksum 2
    }__attribute__((packed));"""

	__slots__ = ("checksum", "filesize", "serial", "run_type", "fpl_platform", "fpl_lot", "mode_version_or_adhesive_run_num", "waveform_version", "waveform_subversion", "waveform_type", "fpl_size", "mfg_code", "waveform_tuning_bias_or_rev", "fpl_rate", "unknown0", "vcom_shifted", "unknown1", "xwia", "cs1", "wmta", "fvsn", "luts", "mc", "trc", "advanced_wfm_flags", "eb", "sb", "reserved0_1", "reserved0_2", "reserved0_3", "reserved0_4", "reserved0_5", "cs2")
	structStr = "IIIBBHBBBBBBBBBBHHBBHBBBBBBBBBBBBBB"
	parser = struct.Struct(structStr)
	structSize = struct.calcsize(structStr)

	def __init__(self, data: bytes):
		self.checksum, self.filesize, self.serial, self.run_type, self.fpl_platform, self.fpl_lot, self.mode_version_or_adhesive_run_num, self.waveform_version, self.waveform_subversion, self.waveform_type, self.fpl_size, self.mfg_code, self.waveform_tuning_bias_or_rev, self.fpl_rate, self.unknown0, self.vcom_shifted, self.unknown1, xwia_LO, xwia_HI, self.cs1, wmta_LO, wmta_HI, self.fvsn, self.luts, self.mc, self.trc, self.advanced_wfm_flags, self.eb, self.sb, self.reserved0_1, self.reserved0_2, self.reserved0_3, self.reserved0_4, self.reserved0_5, self.cs2 = self.__class__.parser.unpack(data[: self.__class__.structSize])
		self.xwia = xwia_HI << 16 | xwia_LO
		self.wmta = wmta_HI << 16 | wmta_LO

	def __bytes__(self):
		xwia_HI = self.xwia >> 16
		xwia_LO = self.xwia & 0xFF
		wmta_HI = self.wmta >> 16
		wmta_LO = self.wmta & 0xFF
		return self.__class__.parser.pack((self.checksum, self.filesize, self.serial, self.run_type, self.fpl_platform, self.fpl_lot, self.mode_version_or_adhesive_run_num, self.waveform_version, self.waveform_subversion, self.waveform_type, self.fpl_size, self.mfg_code, self.waveform_tuning_bias_or_rev, self.fpl_rate, self.unknown0, self.vcom_shifted, self.unknown1, xwia_LO, xwia_HI, self.cs1, wmta_LO, wmta_HI, self.fvsn, self.luts, self.mc, self.trc, self.advanced_wfm_flags, self.eb, self.sb, self.reserved0_1, self.reserved0_2, self.reserved0_3, self.reserved0_4, self.reserved0_5, self.cs2))


class pointer:
	"""
    struct pointer {
                    uint16_t addr_LO;
                    uint8_t addr_HI;
                    uint8_t checksum;
    }__attribute__((packed));"""

	__slots__ = ("addr", "checksum")
	structStr = "HBB"
	parser = struct.Struct(structStr)
	structSize = struct.calcsize(structStr)

	def __init__(self, data: bytes):
		addr_LO, addr_HI, self.checksum = self.__class__.parser.unpack(data[: self.__class__.structSize])
		self.addr = addr_HI << 16 | addr_LO


def temp_range(data: bytes):
	"""
    struct temp_range {
            uint8_t from;
            uint8_t to;
    };"""
	return range(*struct.unpack("HBB", data))


class packed_state:
	"""
    struct packed_state {
            uint8_t s0:2;
            uint8_t s1:2;
            uint8_t s2:2;
            uint8_t s3:2;
    }__attribute__((packed));"""

	__slots__ = ("s0", "s1", "s2", "s3")

	def __init__(self, b):
		self.s0 = b & 0b11
		self.s1 = (b >> 2) & 0b11
		self.s2 = (b >> 4) & 0b11
		self.s3 = (b >> 6) & 0b11


unpacked_state = packed_state
"""
struct unpacked_state {
	uint8_t s0;
	uint8_t s1;
	uint8_t s2;
	uint8_t s3;
}__attribute__((packed));
"""


def get_bits_per_pixel(header: waveform_data_header) -> uint8_t:
	return 5 if (header.luts & 0xC) == 4 else 4


def compare_checksum(data: str, header: waveform_data_header) -> int:
	if crc32(b"\0\0\0\0" + data[4 : header.filesize]) != header.checksum:
		return -1
	return 0


def add_addr(addrs: typing.List[uint32_t], addr: uint32_t, max: uint32_t) -> int:
	# ToDo: replace with a heap
	i: uint32_t = 0

	for i in range(0, max):
		if addrs[i] == addr:
			return 0
			# this address was already in the array
		if not addrs[i]:
			addrs[i] = addr
			return 1  # added

	print("Encountered more addresses than our hardcoded max", file=sys.stderr)
	return -1


def print_header(header: waveform_data_header, is_wbf: int) -> None:
	print("Header info:")
	if is_wbf:
		print("	File size (according to header): " + str(header.filesize) + " bytes")
	print("	Serial number: " + str(header.serial) + "")
	print("	Run type: " + hex(header.run_type) + " | " + get_desc(run_types, header.run_type, None) + "")
	print("	Manufacturer code: " + hex(header.mfg_code) + " | " + get_desc_mfg_code(header.mfg_code) + "")

	print("	Frontplane Laminate (FPL) platform: " + hex(header.fpl_platform) + " | " + get_desc(fpl_platforms, header.fpl_platform, None) + "")
	print("	Frontplane Laminate (FPL) lot: " + str(header.fpl_lot) + "")
	print("	Frontplane Laminate (FPL) size: " + hex(header.fpl_size) + " | " + get_desc(fpl_sizes, header.fpl_size, None) + "")
	print("	Frontplane Laminate (FPL) rate: " + hex(header.fpl_rate) + " | " + get_desc(fpl_rates, header.fpl_rate, None) + "")

	print("	Waveform version: " + str(header.waveform_version) + "")
	print("	Waveform sub-version: " + str(header.waveform_subversion) + "")

	print("	Waveform type: " + hex(header.waveform_type) + " | " + get_desc(waveform_types, header.waveform_type, None) + "")

	# if waveform_type is WJ or earlier
	# then waveform_tuning_bias_or_rev is the tuning bias.
	# if it is WR type or later then it is the revision.
	# if it is in between then we don't know.
	if header.waveform_type <= 0x15:  # WJ type or earlier
		print("	Waveform tuning bias: " + hex(header.waveform_tuning_bias_or_rev) + " | " + get_desc(waveform_tuning_biases, header.waveform_tuning_bias_or_rev, None) + "")
		print("	Waveform revision: Unknown")
	elif header.waveform_type >= 0x2B:  # WR type or later
		print("	Waveform tuning bias: Unknown")
		print("	Waveform revision: " + str(header.waveform_tuning_bias_or_rev) + "")
	else:
		print("	Waveform tuning bias: Unknown")
		print("	Waveform revision: Unknown")

	# if fpl_platform is < 3 then
	# mode_version_or_adhesive_run_num is the adhesive run number
	if header.fpl_platform < 3:
		print("	Adhesive run number: " + str(header.mode_version_or_adhesive_run_num) + "")
		print("	Mode version: Unknown")
	else:
		print("	Adhesive run number: Unknown")
		print("	Mode version: " + hex(header.mode_version_or_adhesive_run_num) + " | " + get_desc(mode_versions, header.mode_version_or_adhesive_run_num, None) + "")

	print("	Number of modes in this waveform: " + str(header.mc + 1) + "")
	print("	Number of temperature ranges in this waveform: " + str(header.trc + 1) + "")

	print("	4 or 5-bits per pixel: " + str(get_bits_per_pixel(header)) + "")

	print("")


def get_waveform_length(wav_addrs: typing.List[uint32_t], wav_addr: uint32_t) -> uint32_t:
	i: uint32_t = 0

	for i in range(MAX_WAVEFORMS - 1):
		if wav_addrs[i] == wav_addr:
			if not wav_addrs[i]:
				return 0

			return wav_addrs[i + 1] - wav_addr
	return 0


def toS(n: int):
	if n & 0x80:
		return n - 0x80
	else:
		return n


def parse_waveform(data: bytes, wav_addrs: typing.List[uint32_t], wav_addr: uint32_t, outfile: io.IOBase) -> int:
	i: uint32_t = 0
	j: uint32_t = 0
	s: packed_state
	u: unpacked_state
	count: uint16_t
	fc_active: int = 0
	zero_pad: int = 0
	written: size_t
	state_count: uint16_t = 0
	waveform: bytes = data[:wav_addr]

	# TODO
	# We are cutting off the last two bytes
	# since we don't know what they are.
	# See section on unsolved mysteries at the top of this file.
	l: uint32_t = get_waveform_length(wav_addrs, wav_addr) - 2
	if not l:
		printf("Could not find waveform length", file=stderr)
		return -1

	while i < l - 1:
		print(i, hex(waveform[i]))
		# 0xfc is a start and end tag for a section
		# of one-byte bit-patterns with an assumed count of 1
		if (waveform[i] & 0xFF) == 0xFC:
			fc_active = 0 if fc_active else 1
			i += 1
			continue

		s = packed_state(waveform[i])

		if fc_active:  # 1-byte pattern (count is always 1)
			count = 1
			zero_pad = 1
			i += 1
		else:  # // 2-byte pattern (second byte is count)
			if i >= l - 1:  #
				count = 1
			else:
				count = (waveform[i + 1] & 0xFF) + 1

			zero_pad = 0
			i += 2

		# print("count {:d}".format(count))
		state_count += (count * 4) & 0xFFFF

		if outfile:
			for j in range(count):
				outfile.write(struct.pack("BBBB", s.s0, s.s1, s.s2, s.s3))

	return state_count


def parse_temp_ranges(header: waveform_data_header, data: str, tr_start: str, tr_count: uint8_t, wav_addrs: typing.List[uint32_t], first_pass: int, outfile: io.IOBase, do_print: int) -> int:
	tr: pointer
	checksum: uint8_t
	i: uint8_t
	state_count: uint16_t
	written: size_t
	ftable: long
	fprev: long
	fcur: long
	tr_addrs: typing.List[uint32_t] = [0] * 256
	# temperature range addresses for output file
	tr_table_addr: uint32_t
	# temperature range table output start address

	if not tr_count:
		return 0

	# memset(tr_addrs, 0, sizeof(tr_addrs))

	if do_print:
		print("		Temperature ranges: ")

	if outfile:
		ftable = outfile.tell()

		outfile.seek((header.trc + 1) * 8, SEEK_CUR)

	for i in range(0, tr_count):
		if do_print:
			sys.stdout.write("			Checking range {:2d}: ".format(i))

		tr = pointer(tr_start)
		checksum = (tr_start[0] + tr_start[1] + tr_start[2]) & 0xFF
		if checksum != tr.checksum:
			if do_print:
				print("Failed")
			return -1

		if first_pass:
			if add_addr(wav_addrs, tr.addr, MAX_WAVEFORMS) < 0:
				return -1

		else:

			if outfile:

				fprev = outfile.tell()

				if add_addr(tr_addrs, fprev - MYSTERIOUS_OFFSET, MAX_TEMP_RANGES) < 0:
					return -1

				outfile.seek(8, SEEK_CUR)

			state_count = parse_waveform(data, wav_addrs, tr.addr, outfile)
			if state_count < 0:
				return -1

			if do_print:
				print("{:4d} phases ({:4d})".format(state_count >> 8, tr.addr))

			if outfile:
				fcur = outfile.tell()

				outfile.seek(fprev, SEEK_SET)

				# write state count
				written = outfile.write(state_count.pack(">H"))

				outfile.fseek(fcur, SEEK_SET)

		tr_start = tr_start[4:]

	if do_print:
		print("")

	if outfile:
		if write_table(ftable, tr_addrs, outfile, MAX_TEMP_RANGES) < 0:
			print("Error writing temperature range table", file=sys.stderr)
			return -1

	return 0


def parse_modes(header: waveform_data_header, data: str, mode_start: str, mode_count: uint8_t, temp_range_count: uint8_t, wav_addrs: typing.List[uint32_t], first_pass: int, outfile: io.IOBase, do_print: int) -> int:
	mode: pointer
	checksum: uint8_t
	i: uint8_t
	pos: int
	mode_addrs: typing.List[uint32_t] = [0] * 256
	# mode addresses for output file
	mode_table_addr: uint32_t
	# mode table output start address

	if not mode_count:
		return 0

	# memset(mode_addrs, 0, sizeof(mode_addrs))

	if do_print:
		print("Modes: ")

	for i in range(0, mode_count):
		if do_print:
			sys.stdout.write("	Checking mode {:2d}: ".format(i))

		mode = pointer(mode_start)
		checksum = (mode_start[0] + mode_start[1] + mode_start[2]) & 0xFF
		if checksum != mode.checksum:
			if do_print:
				print("Failed")
			return -1

		if outfile:

			pos = outfile.tell() - MYSTERIOUS_OFFSET

			if add_addr(mode_addrs, pos, MAX_MODES) < 0:
				return -1

		if do_print:
			print("Passed")

		if parse_temp_ranges(header, data, data[mode.addr :], temp_range_count, wav_addrs, first_pass, outfile, do_print) < 0:
			return -1

		mode_start = mode_start[4:]

	if outfile:
		# the + 2 is because there is one more temperature range than the
		# count in header.trc and then because these are ranges there is one
		# more temperature than the number of ranges
		mode_table_addr = waveform_data_header.structSize + header.trc + 2

		if write_table(mode_table_addr, mode_addrs, outfile, MAX_MODES) < 0:
			print("Error writing mode table", file=sys.stderr)
			return -1

	return 0


def check_xwia(xwia: str, do_print: int) -> int:
	xwia_len: uint8_t = xwia[0]
	i: uint8_t
	checksum: uint8_t = xwia_len
	non_printables: int = 0

	xwia = xwia[1 : 1 + xwia_len + 1]
	xwia_s = xwia[:-1].decode("ascii")

	for i in range(0, xwia_len):
		if not xwia_s[i].isprintable():
			non_printables += 1

		checksum += xwia[i]

	if do_print:

		sys.stdout.write("Extra Waveform Info (xwia): ")

		if not xwia_len:
			print("None")
		elif non_printables:
			print("(" + str(xwia_len) + " bytes containing " + str(non_printables) + " unprintable characters)")
		else:
			print(xwia_s)

		print("")

	if checksum & 0xFF != xwia[xwia_len]:
		return -1

	return 0


def parse_temp_range_table(table: str, range_count: uint8_t, outfile: io.IOBase, do_print: int) -> int:
	i: uint8_t
	checksum: uint8_t
	written: size_t

	if not range_count:
		return 0

	if do_print:
		print("Supported temperature ranges:")

	checksum = 0
	for i in range(0, range_count):
		rng = range(uint8_t(table[i]), uint8_t(table[i + 1]))
		if do_print:
			print("	" + str(rng.start) + " - " + str(rng.stop) + " °C")

		checksum = uint8_t(checksum + rng.start)

	checksum = uint8_t(checksum + rng.stop)

	if checksum & 0xFF != uint8_t(table[range_count + 1]):
		return -1

	if outfile:
		written = outfile.fwrite(table, 1, range_count + 1)
		if written != range_count + 1:
			printf("Error writing temperature range table to output file: " + strerror(errno) + "\n", file=sys.stderr)
			return -1

	if do_print:
		print("")

	return 0


def write_table(table_addr: uint32_t, addrs: typing.List[uint32_t], outfile: io.IOBase, max: uint32_t) -> int:
	i: int
	written: size_t
	addr: uint32_t
	prev: int

	prev = outfile.tell()
	if prev < 0:
		return -1

	outfile.seek(table_addr, SEEK_SET)

	for i in range(0, max):
		if not addrs[i]:
			break

		addr = addrs[i]

		written = outfile.fwrite(struct.pack("I", addr))
		if written != struct.calcsize("I"):
			fprintf(sys.stderr, "Error writing address table to output file: " + +"\n", strerror(errno))
			return -1

		outfile.seek(4, SEEK_CUR)

	outfile.seek(prev, SEEK_SET)

	return 0


def write_header(outfile: io.IOBase, header: waveform_data_header) -> int:
	written: size_t

	written = outfile.write(header.serialize())
	if written < waveform_data_header.structSize:
		return -1

	return 0


class MainCLI(cli.Application):
	"""Convert a .wbf file to a .wrf file or if no output file is specified display human readable info about the specified .wbf or .wrf file."""

	USAGE = "inkwave file.wbf/file.wrf [-o output.wrf]"

	outfile_path = cli.SwitchAttr("-o", help="Specify output file")
	force_input = cli.SwitchAttr("-f", help="Force inkwave to interpret input file as either .wrf or .wbf format regardless of file extension")

	def main(self, infile_path) -> int:
		infile_path: Path = Path(infile_path)
		infile: io.IOBase = None
		header: waveform_data_header
		# points to `data` at beginning of header
		modes: str
		# points to `data` where the modes table begins
		temp_range_table: str
		# points to `data` where the temp range table begins
		xwia_len: uint32_t
		mode_count: uint8_t
		temp_range_count: uint8_t
		outfile_path: Path = None
		outfile: io.IOBase = None
		force_input: str = self.force_input
		do_print: int = 0
		force: int = 0
		c: int
		unique_waveform_count: uint32_t
		wav_addrs: typing.List[uint32_t] = [0] * MAX_WAVEFORMS
		# waveform addresses in input file
		is_wbf: uint32_t
		to_alloc: size_t

		if self.outfile_path:
			outfile_path = Path(self.outfile_path)

		# memset(wav_addrs, 0, sizeof(wav_addrs))

		# try:
		if force_input:
			if force_input == "wbf":
				is_wbf = 1
			elif force_input == "wrf":
				is_wbf = 0
			else:
				print("Only wbf and wrf format is supported", file=sys.stderr)
				raise Exception
		else:
			if not infile_path.suffix:
				print("File has neither .wbf or .wrf extension", file=sys.stderr)
				print("Consider using `-f` to bypass file format detection", file=sys.stderr)
				raise Exception
			if infile_path.suffix == ".wbf":
				is_wbf = 1
			elif infile_path.suffix == ".wrf":
				is_wbf = 0
			else:
				print("File has neither .wbf or .wrf extension", file=sys.stderr)
				print("Consider using `-f` to bypass file format detection", file=sys.stderr)
				raise Exception

		if not is_wbf and outfile_path:
			print("Conversion from .wrf format not supported", file=sys.stderr)
			raise Exception

		with infile_path.open("rb") as infile:
			st = infile_path.stat()

			if is_wbf:
				to_alloc = st.st_size
			else:
				to_alloc = waveform_data_header.structSize

			with mmap.mmap(infile.fileno(), to_alloc, access=mmap.ACCESS_READ) as data:

				if outfile_path:
					outfile = outfile_path.open("wb")

				if not outfile:
					do_print = 1

				if do_print:
					print("")
					print("File size: " + str(st.st_size) + " bytes")
					print("")

				# data = infile.read(to_alloc)

				# start of header
				header = waveform_data_header(data)

				if is_wbf:
					if header.filesize != st.st_size:
						print("Actual file size does not match file size reported by waveform header", file=sys.stderr)
						raise Exception

				if outfile:
					if get_bits_per_pixel(header) != 4:
						print("This waveform uses 5 bits per pixel which is not yet support", file=sys.stderr)
						raise Exception

				if is_wbf:
					if compare_checksum(data, header) < 0:
						print("Checksum error", file=sys.stderr)
						raise Exception

				if do_print:
					print_header(header, is_wbf)

					if header.fpl_platform < 3:
						print("Modes: Unknown (no mode version specified)")
					else:
						print_modes(header.mc + 1)

				if not is_wbf:
					return 0

				if outfile:
					if write_header(outfile, header) < 0:
						print("Writing header to output failed", file=sys.stderr)
						raise Exception

				# start of temperature range table
				temp_range_table = data[waveform_data_header.structSize :]

				if parse_temp_range_table(temp_range_table, header.trc + 1, outfile, do_print):
					print("Temperature range checksum error", file=sys.stderr)
					raise Exception

				if outfile:
					outfile.seek(8 * (header.mc + 1), SEEK_CUR)

				if header.xwia:  # if xwia is 0 then there is no xwia info
					xwia_len = data[header.xwia]

					if check_xwia(data[header.xwia :], do_print) < 0:
						print("xwia checksum error", file=sys.stderr)
						raise Exception
				else:
					xwia_len = 0

				# first byte of xwia contains the length
				# last byte after xwia is a checksum
				modes = data[header.xwia + 1 + xwia_len + 1 :]

				if parse_modes(header, data, modes, header.mc + 1, header.trc + 1, wav_addrs, 1, None, 0) < 0:
					print("Parse error during first pass", file=sys.stderr)
					raise Exception

				unique_waveform_count = 0
				for wfa in wav_addrs:
					if not wfa:
						break
					unique_waveform_count += 1

				wav_addrs_uniq = wav_addrs[:unique_waveform_count]
				wav_addrs_uniq.sort()
				del wav_addrs_uniq

				if do_print:
					print("Number of unique waveforms: " + str(unique_waveform_count) + "\n\n")

				# add file endpoint to waveform address table
				# since we use this to determine end address of each waveform
				if add_addr(wav_addrs, st.st_size, MAX_WAVEFORMS) < 0:
					print("Failed to add file end address to waveform table.", file=sys.stderr)
					raise Exception

				# parse modes again since we now have all the sorted waveform addresses
				if parse_modes(header, data, modes, header.mc + 1, header.trc + 1, wav_addrs, 0, outfile, do_print) < 0:
					print("Parse error during second pass", file=sys.stderr)
					raise Exception

				return 0

		# finally:
		# 	outfile.__exit__()
		return 1


if __name__ == "__main__":
	MainCLI.run()
