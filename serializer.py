from pyserializable.util import multidelim_generator
import bitstring

_MISSING_ATTR = "'{}' object was missing expected attribute '{}'"


class Serializer(object):
    def __init__(self):
        self._PREFIX = "Serial_"
        self._indexes = {}
        self._attributes = ['cls', 'cls_str', 'normalized_cls_str']

        #  Build indexes into metadata so we can get at it by most properties
        for attr in self._attributes:
            self._indexes[attr] = {}

    def register(self, cls, format, attr_converters=None, fmt_converters=None):
        '''
        cls: The class to register.  This should have a classmethod called
            'deserialize' which has the signature:
                deserialize(cls, instance, **kwargs).
            instance may be an instance of the class, or None if
            only the class was provided.  For each key => value pair,
            the key is an attribute of the instance whose deserialized value
            is value.  In other words, <inst of cls>.key = value
        format: Format string of comma-separated name=format pairs,
            where each name is a string of an attribute on instances
            of cls that can be serialized and deserialized.
            Example: 'r=uint:8, g=uint:8, b=uint:8' would serialize
            the r, g, b attributes on an instance of cls.
        attr_converters: dictionary of name => [func, func] where name
            is a string of an attribute on instances of cls.
            Each function should take one value and return one value.
            The first function should return a value which can be serialized
            according to the format specified in the format string above.
            The second function takes a value which is returned from unpacking
            a bitstring.  The value returned by this function will be inserted
            for the attribute named into an instance of the cls.
        fmt_converters: dictionary of format => func, func much like
            attr_converters, except each key is a string representing a format
            field that may be in the format string above.  The functions are
            identical to those in attr_converters.  For each format key in this
            dictionary, any attribute with the same format string will use these
            converters when serializing/deserializing.

        If an attribute is mapped in attr_converters and its format is
            mapped in fmt_converters, then its attribute converter
            will be used instead of its format converter.
        '''
        metadata = self._generate_metadata(
            cls, format,
            attr_converters=attr_converters,
            fmt_converters=fmt_converters
        )
        for attr, index in self._indexes.items():
            index[metadata[attr]] = metadata

    def serialize(self, obj):
        values = self._get_flat_values(obj)
        fmt = self._metadata_field('cls', obj.__class__, 'flat_format')
        return bitstring.pack(fmt, *values)

    def deserialize(self, cls_or_obj, data, seek=True):
        '''
        Takes a registered class or an instance of a registered class
        and a bitstring.BitStream object and returns an instance of
        the class with the data in the BitStream deserialized into
        the new instance according to the format registered for the class.
        '''
        # An instance of a registered class
        if self._has_registered_class(cls_or_obj.__class__):
            cls = cls_or_obj.__class__
            instance = cls_or_obj
        # If it's registered, it's a class
        elif self._has_registered_class(cls_or_obj):
            cls = cls_or_obj
            instance = None
        else:
            raise ValueError("Don't know how to deserialize {}".format(cls_or_obj))

        kwargs = {}
        if seek:
            data.pos = 0

        cls_format = self._metadata_field('cls', cls, 'compact_format')
        attr_converters = self._metadata_field('cls', cls, 'attr_converters')
        fmt_converters = self._metadata_field('cls', cls, 'fmt_converters')

        for format, name in multidelim_generator(cls_format, ',', '='):
            if self._has_registered_class(format, normalized=True):
                subcls = self._metadata_field('normalized_cls_str', format, 'cls')
                kwargs[name] = self.deserialize(subcls, data, seek=False)
            else:
                value = data.read(format)
                # Check for converters for this object.
                # Attribute converters take precedence.
                if name in attr_converters:
                    value = attr_converters[name][1](value)
                elif format in fmt_converters:
                    value = fmt_converters[format][1](value)
                kwargs[name] = value
        return cls.deserialize(instance, **kwargs)

    def _get_flat_values(self, obj):
        values = []

        cls = obj.__class__
        cls_format = self._metadata_field('cls', cls, 'compact_format')
        attr_converters = self._metadata_field('cls', cls, 'attr_converters')
        fmt_converters = self._metadata_field('cls', cls, 'fmt_converters')

        for format, name in multidelim_generator(cls_format, ',', '='):
            try:
                data = getattr(obj, name)
            except AttributeError:
                raise AttributeError(_MISSING_ATTR.format(cls.__name__, name))

            if self._has_registered_class(format, normalized=True):
                # Serializable object, get its attributes
                sub_values = self._get_flat_values(data)
                values.extend(sub_values)
            else:
                # Attribute converters take precedence.
                if name in attr_converters:
                    data = attr_converters[name][0](data)
                elif format in fmt_converters:
                    data = fmt_converters[format][0](data)
                values.append(data)

        return values

    def _normalized_class_str(self, cls_or_str):
        '''Centralized normalizing logic so we don't have PREFIX sprinkled throughout our functions'''
        if not isinstance(cls_or_str, str):
            cls_or_str = cls_or_str.__name__
        return self._PREFIX + cls_or_str

    def _generate_metadata(self, cls, raw_format, attr_converters=None, fmt_converters=None):
            metadata = {}
            metadata['cls'] = cls
            metadata['cls_str'] = cls.__name__
            metadata['normalized_cls_str'] = self._normalized_class_str(cls)
            metadata['raw_format'] = raw_format

            compact_pieces = []
            flat_pieces = []
            for name, format in multidelim_generator(raw_format, ',', '='):
                if self._has_registered_class(format, normalized=False):
                    compact_pieces.append('{}={}'.format(self._normalized_class_str(format), name))
                    flat_pieces.append(self._metadata_field('cls_str', format, 'flat_format'))
                else:
                    compact_pieces.append('{}={}'.format(format, name))
                    flat_pieces.append(format)
            compact_format = ','.join(compact_pieces)
            flat_format = ','.join(flat_pieces)
            metadata['compact_format'] = compact_format
            metadata['flat_format'] = flat_format

            formats = raw_format.split(',')
            attrs = [fmt.split('=')[0].strip() for fmt in formats]
            metadata['attrs'] = attrs

            metadata['attr_converters'] = attr_converters or {}
            metadata['fmt_converters'] = fmt_converters or {}

            return metadata

    def _metadata_field(self, index_type, index_value, metadata_field):
        '''
        index_type: string of the type of value you're finding metadata by.  Examples include 'cls' or 'raw_format'.
        index_value: value of the previous type.  For 'cls' a class object, for 'raw_format' a format string.
        metadata_field: string of the field type to retrieve.  This can be any of the values for index_type.
        '''
        return self._indexes[index_type][index_value][metadata_field]

    def _has_registered_class(self, cls_or_str, normalized=False):
        '''
        Takes either a class object or the string of a class name.
        normalized: True if the cls string is normalized.
            class: <class 'MySerializableClass'>
            class string: 'MySerializableClass'
            normalized class string: 'Serial_MySerializableClass' (or whatever PREFIX is)
        '''

        if not normalized:
            normalized_name = self._normalized_class_str(cls_or_str)
        else:
            normalized_name = cls_or_str
        normalized_cls_dicts = self._indexes['normalized_cls_str']
        return normalized_name in normalized_cls_dicts
