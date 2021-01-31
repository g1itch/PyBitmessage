Protocol specification
======================

.. warning:: All objects sent on the network should support protocol v3
	     starting on Sun, 16 Nov 2014 22:00:00 GMT.

.. toctree::
   :maxdepth: 2

Common standards
----------------

Hashes
^^^^^^

Most of the time `SHA-512 <http://en.wikipedia.org/wiki/SHA-2>`_ hashes are
used, however `RIPEMD-160 <http://en.wikipedia.org/wiki/RIPEMD>`_ is also used
when creating an address.

A double-round of SHA-512 is used for the Proof Of Work. Example of
double-SHA-512 encoding of string "hello":

::

   hello
   9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043(first round of sha-512)
   0592a10584ffabf96539f3d780d776828c67da1ab5b169e9e8aed838aaecc9ed36d49ff1423c55f019e050c66c6324f53588be88894fef4dcffdb74b98e2b200(second round of sha-512)

For Bitmessage addresses (RIPEMD-160) this would give:

::

   hello
   9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043(first round is sha-512)
   79a324faeebcbf9849f310545ed531556882487e (with ripemd-160)


Common structures
-----------------

All integers are encoded in big endian. (This is different from Bitcoin).

.. list-table:: Message structure
   :header-rows: 1
   :widths: auto

   * - Field Size
     - Description
     - Data type
     - Comments
   * - 4
     - magic
     - uint32_t
     - Magic value indicating message origin network, and used to seek to next
       message when stream state is unknown
   * - 12
     - command
     - char[12]
     - ASCII string identifying the packet content, NULL padded (non-NULL
       padding results in packet rejected)
   * - 4
     - length
     - uint32_t
     - Length of payload in number of bytes. Because of other restrictions,
       there is no reason why this length would ever be larger than 1600003
       bytes. Some clients include a sanity-check to avoid processing messages
       which are larger than this.
   * - 4
     - checksum
     - uint32_t
     - First 4 bytes of sha512(payload)
   * - ?
     - message_payload
     - uchar[]
     - The actual data, a message or an object_. Not to be confused with
       objectPayload.

Known magic values:

+-------------+-------------------+
| Magic value | Sent over wire as |
+=============+===================+
| 0xE9BEB4D9  | E9 BE B4 D9       |
+-------------+-------------------+

Variable length integer
^^^^^^^^^^^^^^^^^^^^^^^

Integer can be encoded depending on the represented value to save space.
Variable length integers always precede an array/vector of a type of data that
may vary in length. Varints MUST use the minimum possible number of bytes to
encode a value. For example, the value 6 can be encoded with one byte therefore
a varint that uses three bytes to encode the value 6 is malformed and the
decoding task must be aborted.

+---------------+----------------+------------------------------------------+
| Value         | Storage length | Format                                   |
+===============+================+==========================================+
| < 0xfd        | 1              | uint8_t                                  |
+---------------+----------------+------------------------------------------+
| <= 0xffff     | 3              | 0xfd followed by the integer as uint16_t |
+---------------+----------------+------------------------------------------+
| <= 0xffffffff | 5              | 0xfe followed by the integer as uint32_t |
+---------------+----------------+------------------------------------------+
| -             | 9              | 0xff followed by the integer as uint64_t |
+---------------+----------------+------------------------------------------+

Variable length string
^^^^^^^^^^^^^^^^^^^^^^

Variable length string can be stored using a variable length integer followed by
the string itself.

+------------+-------------+-----------+----------------------------------+
| Field Size | Description | Data type | Comments                         |
+============+=============+===========+==================================+
| 1+         | length      | var_int   | Length of the string             |
+------------+-------------+-----------+----------------------------------+
| ?          | string      | char[]    | The string itself (can be empty) |
+------------+-------------+-----------+----------------------------------+

Variable length list of integers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

n integers can be stored using n+1 variable length integers where the first
var_int equals n.

+------------+-------------+-----------+----------------------------+
| Field Size | Description | Data type | Comments                   |
+============+=============+===========+============================+
| 1+         | count       | var_int   | Number of var_ints below   |
+------------+-------------+-----------+----------------------------+
| 1+         |             | var_int   | The first value stored     |
+------------+-------------+-----------+----------------------------+
| 1+         |             | var_int   | The second value stored... |
+------------+-------------+-----------+----------------------------+
| 1+         |             | var_int   | etc...                     |
+------------+-------------+-----------+----------------------------+

Network address
^^^^^^^^^^^^^^^

When a network address is needed somewhere, this structure is used. Network
addresses are not prefixed with a timestamp or stream in the version_ message.

.. list-table::
   :header-rows: 1
   :widths: auto

   * - Field Size
     - Description
     - Data type
     - Comments
   * - 8
     - time
     - uint64
     - the Time.
   * - 4
     - stream
     - uint32
     - Stream number for this node
   * - 8
     - services
     - uint64_t
     - same service(s) listed in version
   * - 16
     - IPv6/4
     - char[16]
     - IPv6 address. IPv4 addresses are written into the message as a 16 byte
       `IPv4-mapped IPv6 address <http://en.wikipedia.org/wiki/IPv6#IPv4-mapped_IPv6_addresses>`_
       (12 bytes 00 00 00 00 00 00 00 00 00 00 FF FF, followed by the 4 bytes of
       the IPv4 address).
   * - 2
     - port
     - uint16_t
     - port number

Inventory Vectors
^^^^^^^^^^^^^^^^^

Inventory vectors are used for notifying other nodes about objects they have or
data which is being requested. Two rounds of SHA-512 are used, resulting in a
64 byte hash. Only the first 32 bytes are used; the later 32 bytes are ignored.

Inventory vectors consist of the following data format:

+------------+-------------+-----------+--------------------+
| Field Size | Description | Data type | Comments           |
+============+=============+===========+====================+
| 32         | hash        | char[32]  | Hash of the object |
+------------+-------------+-----------+--------------------+

Encrypted payload
^^^^^^^^^^^^^^^^^

Bitmessage uses `ECIES <https://en.wikipedia.org/wiki/Integrated_Encryption_Scheme>`_ to encrypt its messages. For more information see Encryption

+------------+-------------+-----------+--------------------------------------------+
| Field Size | Description | Data type | Comments                                   |
+============+=============+===========+============================================+
| 16         | IV          | uchar[]   | Initialization Vector used for AES-256-CBC |
+------------+-------------+-----------+--------------------------------------------+
| 2          | Curve type  | uint16_t  | Elliptic Curve type 0x02CA (714)           |
+------------+-------------+-----------+--------------------------------------------+
| 2          | X length    | uint16_t  | Length of X component of public key R      |
+------------+-------------+-----------+--------------------------------------------+
| X length   | X           | uchar[]   | X component of public key R                |
+------------+-------------+-----------+--------------------------------------------+
| 2          | Y length    | uint16_t  | Length of Y component of public key R      |
+------------+-------------+-----------+--------------------------------------------+
| Y length   | Y           | uchar[]   | Y component of public key R                |
+------------+-------------+-----------+--------------------------------------------+
| ?          | encrypted   | uchar[]   | Cipher text                                |
+------------+-------------+-----------+--------------------------------------------+
| 32         | MAC         | uchar[]   | HMACSHA256 Message Authentication Code     |
+------------+-------------+-----------+--------------------------------------------+

