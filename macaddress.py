# SPDX-License-Identifier: 0BSD
# Copyright 2021 Alexander Kozhevnikov <mentalisttraceur@gmail.com>

"""Like ``ipaddress``, but for hardware identifiers such as MAC addresses."""


__all__ = (
    'HWAddress',
    'OUI',
    'CDI32', 'CDI40',
    'MAC',
    'EUI48', 'EUI60', 'EUI64',
    'parse',
)
__version__ = '1.0.0'


_HEX_DIGITS = "0123456789ABCDEFabcdef"


def _name(obj):
    return type(obj).__name__


def _value_error(value, error, *classes):
    class_names = [cls.__name__ for cls in classes]
    if len(class_names) > 1:
        class_names[-1] = 'or ' + class_names[-1]
    return ValueError(repr(value) + ' ' + error + ' ' + ', '.join(class_names))


class HWAddress:
    """Base class for hardware addresses.

    Can be subclassed to create new address types
    by just defining a couple class attribures.

    Attributes:
        size: An integer defined by each subclass to specify the size
            (in bits) of the hardware address.
        formats: A sequence of format strings defined by each subclass
            to specify what formats the class can parse. The first
            format string is also used for ``repr`` and ``str`` output.
            Each "x" in each format string stands for one hexadecimal
            digit. All other characters are literal. For example, for
            MAC addresses, the format strings are "xx-xx-xx-xx-xx-xx",
            "xx:xx:xx:xx:xx:xx", "xxxx.xxxx.xxxx", and "xxxxxxxxxxxx".
    """

    __slots__ = ('_address',)

    def __init__(self, address):
        """Initialize the hardware address object with the address given.

        Arguments:
            address: An ``int``, ``bytes``, or ``str`` representation
                of the address. If a string, it is parsed using the
                ``formats`` attribute of the class. If a byte string,
                it is read in big-endian. If it is an integer, bytes
                in the integer value are used as the address bytes.

        Raises:
            TypeError: If ``address`` is not one of the valid types.
            ValueError: If ``address`` is a string but does not match
                one of the formats, if ``address`` is a byte string
                but does not match the size, or if ``address`` is an
                integer with a value that is negative or too big.
        """
        if isinstance(address, int):
            overflow = 1 << self.size
            if address >= overflow:
                raise _value_error(address, 'is too big for', type(self))
            if address < 0:
                raise ValueError('hardware address cannot be negative')
            self._address = address
        elif isinstance(address, bytes):
            length = len(address)
            size_in_bytes = (self.size + 7) >> 3
            if length != size_in_bytes:
                raise _value_error(address, 'has wrong length for', type(self))
            offset = (8 - self.size) & 7
            self._address = int.from_bytes(address, 'big') >> offset
        elif isinstance(address, str):
            self._address, _ = _parse(address, type(self))
        else:
            raise TypeError(_name(self) + ' cannot parse ' + _name(address))

    def __repr__(self):
        """Represent the hardware address as an unambiguous string."""
        return _name(self) + '(' + repr(str(self)) + ')'

    def __str__(self):
        """Get the canonical human-readable string of this hardware address."""
        result = []
        offset = (4 - self.size) & 3
        unconsumed_address_value = self._address << offset
        for character in reversed(self.formats[0]):
            if character == 'x':
                nibble = unconsumed_address_value & 0xf
                result.append(_HEX_DIGITS[nibble])
                unconsumed_address_value >>= 4
            else:
                result.append(character)
        return ''.join(reversed(result))

    def __bytes__(self):
        """Get the big-endian byte string of this hardware address."""
        offset = (8 - self.size) & 7
        size_in_bytes = (self.size + 7) >> 3
        return (self._address << offset).to_bytes(size_in_bytes, 'big')

    def __int__(self):
        """Get the raw integer value of this hardware address."""
        return self._address

    def __eq__(self, other):
        """Check if this hardware address is equal to another.

        They are equal if they are instances of the same class
        (including one being a subclass of the other), if they
        have the same size, and if their addresses are equal.
        """
        if not isinstance(other, type(self)) or self.size != other.size:
            return False
        return self._address == other._address

    def __ne__(self, other):
        """Check if this hardware address is not equal to another."""
        if not isinstance(other, type(self)) or self.size != other.size:
            return True
        return self._address != other._address

    def __lt__(self, other):
        """Check if this hardware address is before another.

        Hardware addresses are sorted by their raw bit strings,
        regardless of the exact hardware address class or size.

        For example: ``OUI('00-00-00') < CDI32('00-00-00-00')``,
        and they both are less than ``OUI('00-00-01')``.

        This order intuitively groups address prefixes like OUIs
        with (and just in front of) addresses like MAC addresses
        which have that prefix when sorting a list of them.
        """
        if not isinstance(other, HWAddress):
            return NotImplemented
        this, that = _aligned_address_integers(self, other)
        return this < that or (this == that and self.size < other.size)

    def __le__(self, other):
        """Check if this hardware address is before or equal to another."""
        if not isinstance(other, HWAddress):
            return NotImplemented
        this, that = _aligned_address_integers(self, other)
        return this < that or (this == that and self.size <= other.size)

    def __gt__(self, other):
        """Check if this hardware address is after another."""
        if not isinstance(other, HWAddress):
            return NotImplemented
        this, that = _aligned_address_integers(self, other)
        return this > that or (this == that and self.size > other.size)

    def __ge__(self, other):
        """Check if this hardware address is after or equal to another."""
        if not isinstance(other, HWAddress):
            return NotImplemented
        this, that = _aligned_address_integers(self, other)
        return this > that or (this == that and self.size >= other.size)


def _aligned_address_integers(address1, address2):
    size1 = address1.size
    size2 = address2.size
    if size1 > size2:
        return (int(address1), int(address2) << (size1 - size2))
    else:
        return (int(address1) << (size2 - size1), int(address2))


class OUI(HWAddress):
    """Organizationally Unique Identifier."""

    __slots__ = ()

    size = 24

    formats = (
        'xx-xx-xx',
        'xx:xx:xx',
        'xxxxxx',
    )


class _StartsWithOUI(HWAddress):
    __slots__ = ()

    @property
    def oui(self):
        """Get the OUI part of this hardware address."""
        return OUI(int(self) >> (self.size - OUI.size))


class CDI32(_StartsWithOUI):
    """32-bit Context Dependent Identifier (CDI-32)."""

    __slots__ = ()

    size = 32

    formats = (
        'xx-xx-xx-xx',
        'xx:xx:xx:xx',
        'xxxxxxxx',
    )


class CDI40(_StartsWithOUI):
    """40-bit Context Dependent Identifier (CDI-40)."""

    __slots__ = ()

    size = 40

    formats = (
        'xx-xx-xx-xx-xx',
        'xx:xx:xx:xx:xx',
        'xxxxxxxxxx',
    )


class EUI48(_StartsWithOUI):
    """48-Bit Extended Unique Identifier (EUI-48).

    EUI-48 is also the modern official name for what
    many people are used to calling a "MAC address".
    """

    __slots__ = ()

    size = 48

    formats = (
        'xx-xx-xx-xx-xx-xx',
        'xx:xx:xx:xx:xx:xx',
        'xxxx.xxxx.xxxx',
        'xxxxxxxxxxxx',
    )


class MAC(EUI48):
    """MAC address. A subclass of EUI48.

    There is nothing wrong with using EUI48 for MAC addresses,
    this is just provided as a convenience for the many users
    who will look for "MAC address" without knowing about EUI.

    But it is a subclass instead of just an alias because it
    might be nice in some situations to distinguish in code
    between MAC addresses and other uses of EUI-48.
    """

    __slots__ = ()


class EUI60(_StartsWithOUI):
    """60-Bit Extended Unique Identifier (EUI-60)."""

    __slots__ = ()

    size = 60

    formats = (
        'x.x.x.x.x.x.x.x.x.x.x.x.x.x.x',
        'xx-xx-xx.x.x.x.x.x.x.x.x.x',
        'xxxxxxxxxxxxxxx',
    )


class EUI64(_StartsWithOUI):
    """64-Bit Extended Unique Identifier (EUI-64)."""

    __slots__ = ()

    size = 64

    formats = (
        'xx-xx-xx-xx-xx-xx-xx-xx',
        'xx:xx:xx:xx:xx:xx:xx:xx',
        'xxxx.xxxx.xxxx.xxxx',
        'xxxxxxxxxxxxxxxx',
    )


def parse(string, *classes):
    """Try parsing a string as several hardware address classes at once.

    This is useful when you have one piece of code that can accept user
    input of two or more different hardware addresses or identifiers.
    This lets you can just write

        address = hwaddress.parse(user_input, EUI64, EUI48, ...)

    instead of all of this:

        try:
            hw_address = hwaddress.EUI64(user_input)
        except ValueError:
            try:
                hw_address = hwaddress.EUI48(user_input)
            except ValueError:
                ...

    Arguments:
        string: The string to parse as a hardware address.
        *classes: HWAddress subclasses to try to parse the string as.

    Returns:
        HWAddress: The parsed hardware address.
        None: If no classes were passed in.

    Raises:
        ValueError: If the string could not be parsed as any of the
            given classes.
    """
    if not classes:
        return None
    address, cls = _parse(string, *classes)
    return cls(address)


def _parse(input, *classes):
    length = len(input)
    if length < 1:
        raise ValueError('hardware address cannot be an empty string')
    candidates = {}
    for cls in classes:
        for format in cls.formats:
            if len(format) == length:
                candidates.setdefault(format, cls)
    candidates = sorted(candidates.items())
    address = 0
    start = 0
    end = len(candidates)
    for index in range(length):
        character = input[index]
        if character in _HEX_DIGITS:
            address <<= 4
            address += int(character, 16)
            character = 'x'
        while start < end and candidates[start][0][index] < character:
            start += 1
        while start < end and candidates[end - 1][0][index] > character:
            end -= 1
        if start >= end:
            raise _value_error(input, 'cannot be parsed as', *classes)
    _, cls = candidates[start]
    offset = (4 - cls.size) & 3
    address >>= offset
    return address, cls