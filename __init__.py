import bitstring

__all__ = ['Serializer', 'autoserializer', 'serialize', 'deserialize']
_MISSING_ATTR = "'{}' object was missing expected attribute '{}'"
_AUTO_MISSING_ATTR = "Built-in deserialization method expected value for attribute '{}' but found none."


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
        '''
        If obj is an instance of a class that has been registered,
        returns a bitstring.BitStream object with the serialized
        representation of the object according to its format.
        '''
        stream = bitstring.BitStream()
        cls = obj.__class__

        cls_format = self._metadata_field('cls', cls, 'compact_format')
        attr_converters = self._metadata_field('cls', cls, 'attr_converters')
        fmt_converters = self._metadata_field('cls', cls, 'fmt_converters')

        for argstr in cls_format.split(','):
            format, name = argstr.split('=')
            try:
                data = getattr(obj, name)
            except AttributeError:
                raise AttributeError(_MISSING_ATTR.format(cls.__name__, name))
            if self._has_registered_class(format, normalized=True):
                substream = self.serialize(data)
            else:
                # Check for converters for this object.
                # Attribute converters take precedence.
                if name in attr_converters:
                    data = attr_converters[name][0](data)
                elif format in fmt_converters:
                    data = fmt_converters[format][0](data)
                substream = bitstring.pack(format, data)
            stream.append(substream)
        return stream

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

        for argstr in cls_format.split(','):
            format, name = argstr.split('=')
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

            pieces = raw_format.split(',')
            compact_pieces = []
            for piece in pieces:
                name, format = [p.strip() for p in piece.split('=')]
                if self._has_registered_class(format, normalized=False):
                    compact_pieces.append('{}={}'.format(self._normalized_class_str(format), name))
                else:
                    compact_pieces.append('{}={}'.format(format, name))
            compact_format = ','.join(compact_pieces)
            metadata['compact_format'] = compact_format

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


def _autoserialized(serializer, cls):
    '''
    Decorator that automatically registers a class as serializable
        and generates a deserialize method for a class.
    The class must have a 'serial_format' attribute which is
        a format string used to serialize/deserialize attributes
        on an instance of itself.
    The class must also allow an empty constructor.  If the init
        function requires arguments, it cannot be autoserialized.
    If the attribute 'serial_attr_converters' is found, it will
        be passed to the register function as the attr_converters
        dictionary.
    If the attribute 'serial_fmt_converters' is found, it will
        be passed to the register function as the fmt_converters
        dictionary.

    See the register method for more details on how converters are used.
    '''
    attr_converters = getattr(cls, 'serial_attr_converters', None)
    fmt_converters = getattr(cls, 'serial_fmt_converters', None)
    serializer.register(
        cls, cls.serial_format,
        attr_converters=attr_converters,
        fmt_converters=fmt_converters
    )

    @classmethod
    def deserialize(cls, instance, **kwargs):
        if instance is None:
            instance = cls()
        for attr in serializer._metadata_field('cls', cls, 'attrs'):
            try:
                setattr(instance, attr, kwargs[attr])
            except KeyError:
                raise AttributeError(_AUTO_MISSING_ATTR.format(attr))
        return instance

    cls.deserialize = deserialize

    # Hook up the serializer so that we don't need to know it to serialize/deserialize objects of this type
    cls._serializer = serializer

    return cls


def autoserializer(serializer):
    return lambda cls: _autoserialized(serializer, cls)


def serialize(obj):
    '''
    If the object's class has a _serializer field, uses that serializer.
    Otherwise, raises an AttributeError.
    '''
    cls = obj.__class__
    if hasattr(cls, '_serializer'):
        return cls._serializer.serialize(obj)
    else:
        raise AttributeError("Couldn't find a serializer for object of type '{}'".format(cls.__name__))


def deserialize(cls_or_obj, data, seek=True):
    '''
    If the class (or object's class) has a _serializer field, uses that serializer.
    Otherwise, raises an AttributeError.
    '''
    try:
        serializer = cls_or_obj._serializer
    except:
        try:
            serializer = cls_or_obj.__class__._serializer
        except:
            raise AttributeError("Couldn't find a serializer to deserialize with.")
    return serializer.deserialize(cls_or_obj, data, seek=seek)