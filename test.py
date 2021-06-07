from hypothesis import given
from hypothesis.strategies import composite, integers, lists, sampled_from

from macaddress import *


@composite
def _addresses(draw, random_formats=0):
    address_sizes = integers(min_value=1, max_value=64)
    size_in_bits = draw(address_sizes)
    Class = draw(_address_classes(size_in_bits, random_formats))
    address_as_an_integer = draw(_address_integers(size_in_bits))
    return Class(address_as_an_integer)


@composite
def _addresses_with_several_random_formats(draw):
    random_formats = draw(integers(min_value=2, max_value=8))
    return draw(_addresses(random_formats=random_formats))


@composite
def _lists_of_distinctly_formatted_addresses(draw):
    return draw(lists(
        _addresses(random_formats=1),
        min_size=2,
        max_size=8,
        unique_by=lambda address: address.formats[0],
    ))


@composite
def _address_classes(draw, size_in_bits, random_formats=0):
    size_in_nibbles = (size_in_bits + 3) >> 2

    if random_formats > 0:
        format_strings = draw(lists(
            _address_format_strings(size_in_nibbles),
            min_size=random_formats,
            max_size=random_formats,
        ))
    else:
        format_string = 'x' * size_in_nibbles
        format_strings = (format_string,)

    class Class(HWAddress):
        size = size_in_bits
        formats = format_strings
        def __repr__(self):
            name = type(self).__name__
            address = repr(self._address)
            formats = repr(type(self).formats)
            return ' '.join(('<', name, address, formats, '>'))

    # This helpfully shows the size of each class and instance in
    # pytest output when Hypothesis finds test-failing examples:
    Class.__name__ += repr(size_in_bits)
    Class.__qualname__ += repr(size_in_bits)

    return Class


def _address_integers(size_in_bits):
    return integers(min_value=0, max_value=((1 << size_in_bits) - 1))


_address_format_characters = sampled_from('x-:.')


@composite
def _address_format_strings(draw, size_in_nibbles):
    characters = []
    while size_in_nibbles:
        character = draw(_address_format_characters)
        if character == 'x':
            size_in_nibbles -= 1
        characters.append(character)
    return ''.join(characters)


@given(_addresses())
def test_int(address):
    Class = type(address)
    assert Class(int(address)) == address


@given(_addresses())
def test_bytes(address):
    Class = type(address)
    assert Class(bytes(address)) == address


@given(_addresses(random_formats=1))
def test_str(address):
    Class = type(address)
    assert Class(str(address)) == address


@given(_addresses(random_formats=1))
def test_parse(address):
    Class = type(address)
    assert parse(str(address), Class) == address


@given(_addresses_with_several_random_formats())
def test_alternate_str(address):
    Class = type(address)
    for format in Class.formats:
        # Override instance formats to make this format the only
        # format, because it will stringify using the first one:
        address.formats = (format,)
        # The class still has the original formats, so this loop
        # tests if the constructor parses each alternate format
        # successfully, whether or not it is the first one:
        assert Class(str(address)) == address


@given(_lists_of_distinctly_formatted_addresses())
def test_alternate_parse(addresses):
    classes = [type(address) for address in addresses]
    for address in addresses:
        assert parse(str(address), *classes) == address


@given(_addresses(), _addresses())
def test_ordering(address1, address2):
    assert (address1 <  address2) == (_bits(address1) <  _bits(address2))
    assert (address1 <= address2) == (_bits(address1) <= _bits(address2))
    assert (address1 >  address2) == (_bits(address1) >  _bits(address2))
    assert (address1 >= address2) == (_bits(address1) >= _bits(address2))


def _bits(address):
    size = address.size
    address = address._address
    bits = []
    while size:
        least_significant_bit = address & 1
        bits.append(least_significant_bit)
        address >>= 1
        size -= 1
    return ''.join(map(str, reversed(bits)))


def test_provided_classes():
    for Class in OUI, CDI32, CDI40, MAC, EUI48, EUI60, EUI64:
        for format in Class.formats:
            assert (Class.size + 3) >> 2 == sum(1 for x in format if x == 'x')