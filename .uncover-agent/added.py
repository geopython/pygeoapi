    elif _is_numpy_scalar(obj, 'integer'):
    elif _is_numpy_scalar(obj, 'floating'):
    elif _is_numpy_scalar(obj, 'bool', 'bool_'):
        return bool(obj)
def _is_numpy_scalar(obj: Any, *type_names: str) -> bool:
    """
    helper function to check whether an object is a NumPy scalar of
    a given abstract type (e.g. `integer` covers `int8` to `uint64`),
    without requiring NumPy to be installed

    :param obj: `object` to be evaluated
    :param type_names: NumPy type names to match

    :returns: `bool` of whether the object is a matching NumPy scalar
    """

    return any(cls.__module__ == 'numpy' and cls.__name__ in type_names
               for cls in type(obj).__mro__)


import json
import numpy as np


@pytest.mark.parametrize('value,expected', [
    (np.int8(-3), -3),
    (np.int16(7), 7),
    (np.int32(7), 7),
    (np.int64(7), 7),
    (np.uint8(255), 255),
    (np.uint64(2**64 - 1), 2**64 - 1),
    (np.float16(0.5), 0.5),
    (np.float32(0.5), 0.5),
    (np.float64(0.5), 0.5),
    (np.bool_(True), True),
])
def test_json_serial_numpy_scalars(value, expected):
    result = util.json_serial(value)
    assert result == expected
    assert type(result) is type(expected)
    assert json.loads(json.dumps({'value': value},
                                 default=util.json_serial)) == {
        'value': expected}