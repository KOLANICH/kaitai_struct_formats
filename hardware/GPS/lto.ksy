meta:
  id: lto
  file-extension: dat
  title: Broadcom Long Term Orbits (for now v1)
  endian: le
  license: Unlicense
doc: |
  Broadcom Long Term Orbits is a file downloaded from [Broadcom servers](http://gllto{,1,2}.glpals.com/{2,4,7,30}day/{,glo/}v{2,3,4,5,6}/latest/lto2.dat) ([in fact it is Amazon S3 cloud](http://gllto.glpals.com/)) and passed into GPS receiver to allow it work with Assisted GPS. The format is totally undocumented and I have found no references of it in the Net.
  
  2017-10-02/v1.2 lto.dat:
  DECIMAL       HEXADECIMAL     DESCRIPTION
  --------------------------------------------------------------------------------
  56            0x38            Raw deflate compression stream
  85            0x55            Raw deflate compression stream
  93            0x5D            Raw deflate compression stream
  101           0x65            Raw deflate compression stream
  120           0x78            Raw deflate compression stream
  184           0xB8            Raw deflate compression stream
  325           0x145           Raw deflate compression stream
  333           0x14D           Raw deflate compression stream
  341           0x155           Raw deflate compression stream
  349           0x15D           Raw deflate compression stream
  376           0x178           Raw deflate compression stream
  440           0x1B8           Raw deflate compression stream
  504           0x1F8           Raw deflate compression stream
  741           0x2E5           Raw deflate compression stream
  788           0x314           Raw deflate compression stream
  859           0x35B           Raw deflate compression stream
  879           0x36F           Raw deflate compression stream
  924           0x39C           Raw deflate compression stream
  1050          0x41A           Raw deflate compression stream
  1052          0x41C           Raw deflate compression stream
  1057          0x421           Raw deflate compression stream
  1063          0x427           Raw deflate compression stream
  1333          0x535           Raw deflate compression stream
  1376          0x560           Raw deflate compression stream
  1723          0x6BB           Raw deflate compression stream
  1732          0x6C4           Raw deflate compression stream
  1738          0x6CA           Raw deflate compression stream
  1808          0x710           Raw deflate compression stream
  1874          0x752           Raw deflate compression stream
  1879          0x757           Raw deflate compression stream
  
seq:
  - id: signature
    type: u4
  - id: unkn01
    type: u4
  - id: unkn02
    type: u4
  - id: unkn0
    size: 16
  - id: unkn03
    type: u4
  - id: unkn04
    type: u4
    
  - id: len1
    type: u4
  - id: unkn1
    type: rec0
    repeat: expr
    repeat-expr: len1
  - id: unkn2
    type: rec1
    repeat: expr
    repeat-expr: len1
    
  - id: unkn30
    type: u4
  - id: unkn31
    type: u4
  - id: unkn32
    type: u4
  - id: unkn33
    type: u4
    
  - id: len2
    type: u4
  - id: unkn4
    type: rec0
    repeat: expr
    repeat-expr: len2
    
  - id: len3
    type: u4
  - id: unkn5
    type: rec0
    repeat: expr
    repeat-expr: len3

  - id: unkn6
    type: rec1
    repeat: expr
    # 65      +4.679842862451558 *days
    # 65      +4.6303571428571431*days
    # 64.60779+4.7211724345238109*days
    repeat-expr: 74 # {1-5}.2.lto.dat
    #repeat-expr: 84 # {1-5}.4.lto.dat
    #repeat-expr: 97 # {1-5}.7.lto.dat
    #repeat-expr: 206 # 2.30.lto.dat
  
  - id: unkn7
    type: u4
  - id: unkn71
    type: u4
  - id: unkn72
    type: u4
  
  - id: unkn10
    size: 4
  - id: unkn11
    size: 4
  - id: unkn12
    size: 22
  
  - id: unkn13
    type: rec2
    repeat: expr
    repeat-expr: 8
  - id: unkn14
    size: 0x8AC
  - id: unkn15
    type: u4
  - id: unkn16
    type: u2
  - id: unkn17
    type: u2
  - id: unkn18
    type: u2
  - id: unkn19
    type: u4
  - id: unkn20
    type: u4
  - id: unkn21
    type: u4
  - id: unkn22
    type: u4
  - id: unkn23
    type: u4
  - id: unkn24
    type: u4
  - id: unkn25
    type: u4
  - id: unkn26
    type: u4
  - id: unkn27
    type: u4
  - id: unkn28
    type: u4
  - id: unkn29
    type: u4
  - id: unkn34
    type: u4
  - id: unkn35
    type: u4
  - id: unkn36
    type: u4
  - id: unkn37
    type: u4
  - id: unkn38
    type: u4
  - id: unkn39
    type: u4
  - id: str_len
    type: u4
  - id: some_str
    type: str
    encoding: ascii
    size: str_len
types:
  rec0:
    #just 2 int record, may be different types
    seq:
      - id: unkn0
        type: u4
        repeat: expr
        repeat-expr: 2
  rec1:
    seq:
      - id: size
        type: u4
      - id: payload
        size: size
        #type: u4
        #repeat: expr
        #repeat-expr: size/4
  rec2:
    seq:
      - id: payload
        type: u2
        repeat: expr
        repeat-expr: 72
