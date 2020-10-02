meta:
  id: eink_wbf
  title: E-Ink Corporation Waveform blob
  license: GPL-2.0
  file-extension: wbf
  endian: le
  xref:
    wikidata: Q189897

doc:
  Files can be downloaded from
    https://openinkpot.org/pub/contrib/n516-waveforms/default.wbf
  and also extracted from devices firmwares (https://github.com/Synacktiv-contrib/stuffz/ is helpful), or dumped from chips using https://github.com/julbouln/ice40_eink_controller/tree/master/utils/wbf_dump

doc-ref:
  - https://github.com/fread-ink/inkwave
  - https://web.archive.org/web/http://essentialscrap.com/eink/
  - https://web.archive.org/web/20200206095814/http://git.spritesserver.nl/espeink.git/
  - https://github.com/julbouln/ice40_eink_controller/tree/master/utils/wbf_dump

instances:
  mysterious_offset:
    value: 63
    doc: for unknown reasons addresses in the .wrf file need to be offset by this count of bytes

seq:
  - id: header
    type: header
  - id: temp_range_table
    type: temp_range_table
types:
  header:
    -orig-id: waveform_data_header
    seq:
      - id: checksum
        type: u4
      - id: size
        -orig-id: filesize
        type: u4
      - id: serial
        type: u4
      - id: run_type
        type: u1
      - id: fpl_platform
        type: u1
      - id: fpl_lot
        type: u2
      - id: mode_version_or_adhesive_run_num
        type: u1
      - id: waveform_version
        type: u1
      - id: waveform_subversion
        type: u1
      - id: waveform_type
        type: u1
      - id: fpl_size
        type: u1
        doc: aka panel_size
      - id: mfg_code
        type: u1
        doc: aka amepd_part_number
      - id: waveform_tuning_bias_or_rev
        type: u1
      - id: fpl_rate
        type: u1
        doc: aka frame_rate
      - id: unknown0
        type: u1
      - id: vcom_shifted
        type: u1
      - id: unknown1
        type: u2
      - id: xwia
        type: u3
        doc: address of extra waveform information
      - id: cs1
        type: u1
        doc: checksum 1
      - id: wmta
        type: u3
      - id: fvsn
        type: u1
      - id: luts
        type: u1
      - id: mode_count
        -orif-id: mc
        type: u1
        doc: "length of mode table - 1"
      - id: temperature_range_count
        -orif-id: trc
        type: u1
        doc: "length of temperature table - 1"
      - id: advanced_wfm_flags
        type: u1
      - id: eb
        type: u1
      - id: sb
        type: u1
      - id: reserved_or_unkn
        size: 5
      - id: cs2
        type: u1
        doc: checksum 2
    instances:
      bits_per_pixel:
        value: "((luts & 0xc) == 4) ? 5 : 4"
  ptr:
    seq:
      - id: raw_ptr
        -orig-id: mode_start
        type: u4
    instances:
      ptr:
        value: raw_ptr & 0x00FFFFFF
      checksum:
        value: raw_ptr >> 24
      computed_checksum:
        value: (ptr & 0xFF + (ptr >> 8) & 0xFF + (ptr >> 16) & 0xFF)
  temp_range_table:
    seq:
      - id: ranges
        type: range
        repeat: expr
        repeat-expr: _rrot.header.range_count - 1
      - id: checksum
        type: u1
        doc: "must be equal to sum of all from + last to"
    types:
      range:
        seq:
          - id: from
            type: u1
          - id: to
            type: u1
  modes:
    seq:
      - id: modes
        type: ptr
        repeat: expr
        repeat-expr: mode_count
    types:
      parse_temp_ranges(header, data, data + mode->addr, temp_range_count, wav_addrs, first_pass, outfile, do_print) < 0
      temp_ranges:
        seq:
          - id: ranges
            type: temp_range
            repeat: expr
            repeat-expr: tr_count
        types:
          temp_range:
            seq:
              - id: ptr
                type: ptr
            instances:
              state_count = parse_waveform(data, wav_addrs, tr->addr, outfile);
            types:
              waveform:
                seq:

uint32_t get_waveform_length(uint32_t* wav_addrs, uint32_t wav_addr) {
  uint32_t i;

  for(i=0; i < MAX_WAVEFORMS - 1; i++) {
    if(wav_addrs[i] == wav_addr) {
      if(!wav_addrs[i]) return 0;

      return wav_addrs[i+1] - wav_addr;
    }
  }
  return 0;
}


                char* waveform = data + wav_addr;
                get_waveform_length(wav_addrs, wav_addr) - 2;
while(i < len - 1) {
    // 0xfc is a start and end tag for a section
    // of one-byte bit-patterns with an assumed count of 1
    if((uint8_t) waveform[i] == 0xfc) {
      fc_active = (fc_active) ? 0 : 1;
      i++;
      continue;
    }

    s = (struct packed_state*) waveform + i;

    if(fc_active) { // 1-byte pattern (count is always 1)
      count = 1;
      zero_pad = 1;
      i++;
    } else { // 2-byte pattern (second byte is count)
      if(i >= len - 1) {
        count = 1;
      } else {
        count = (uint8_t) waveform[i + 1] + 1;
      }
      zero_pad = 0;
      i += 2;
    }

    state_count += count * 4;

    if(outfile) {

      u.s0 = s->s0;
      u.s1 = s->s1;
      u.s2 = s->s2;
      u.s3 = s->s3;

      for(j=0; j < count; j++) {

        written = fwrite(&u, 1, sizeof(u), outfile);
        if(written != sizeof(u)) {
          fprintf(stderr, "Error writing waveform to output file: %s\n", strerror(errno));
          return -1;
        }
      }
    }
  }

  return state_count;
}
