# Data structure manipulations and conversions:

from collections import OrderedDict

import numpy as np

from tvb_epilepsy.base.utils.log_error_utils import warning, raise_value_error, raise_import_error


def vector2scalar(x):
    if not (isinstance(x, np.ndarray)):
        return x
    else:
        y=np.squeeze(x)
    if all(y.squeeze()==y[0]):
        return y[0]
    else:
        return reg_dict(x)


def list_of_strings_to_string(lstr, sep=","):
    str = lstr[0]
    for s in lstr[1:]:
        str += sep+s
    return str


def dict_str(d):
    s = "{"
    for key, value in d.iteritems():
        s += ("\n" + key + ": " + str(value))
    s += "}"
    return s


def isequal_string(a, b, case_sensitive=False):
    if case_sensitive:
        return a == b
    else:
        try:
            return a.lower() == b.lower()
        except AttributeError:
            warning("Case sensitive comparison!")
            return a == b


def formal_repr(instance, attr_dict):
    """ A formal string representation for an object.
    :param attr_dict: dictionary attribute_name: attribute_value
    :param instance:  Instance to read class name from it
    """
    class_name = instance.__class__.__name__
    formal = class_name + "{"
    for key, val in sort_dict(attr_dict).iteritems():
        if isinstance(val, dict):
            formal += "\n" + key + "=["
            for key2, val2 in val.iteritems():
                formal += "\n" + str(key2) + " = " + str(val2)
            formal += "]"
        else:
            formal += "\n" + str(key) + " = " + str(val)
    return formal + "}"


def obj_to_dict(obj):
    """
    :param obj: Python object to introspect
    :return: dictionary after recursively taking obj fields and their values
    """
    if obj is None:
        return obj
    if isinstance(obj, (str, int, float)):
        return obj
    if isinstance(obj, (np.float32,)):
        return float(obj)
    if isinstance(obj, (np.ndarray)):
        return obj.tolist()
    if isinstance(obj, list):
        ret = []
        for val in obj:
            ret.append(obj_to_dict(val))
        return ret
    ret = {}
    for key in obj.__dict__:
        val = getattr(obj, key, None)
        ret[key] = obj_to_dict(val)
    return ret


def reg_dict(x, lbl=None, sort=None):
    """
    :x: a list or np vector
    :lbl: a list or np vector of labels
    :return: dictionary
    """
    if not (isinstance(x, (str, int, float, list, np.ndarray))):
        return x
    else:
        if not (isinstance(x, list)):
            x = np.squeeze(x)
        x_no = len(x)
        if not (isinstance(lbl, (list, np.ndarray))):
            lbl = np.repeat('', x_no)
        else:
            lbl = np.squeeze(lbl)
        labels_no = len(lbl)
        total_no = min(labels_no, x_no)
        if x_no <= labels_no:
            if sort=='ascend':
                ind = np.argsort(x).tolist()
            elif sort == 'descend':
                ind = np.argsort(x)
                ind = ind[::-1].tolist()
            else:
                ind = range(x_no)
        else:
            ind = range(total_no)
        d = OrderedDict()
        for i in ind:
            d[str(i) + '.' + str(lbl[i])] = x[i]
        if labels_no > total_no:
            ind_lbl = np.delete(np.array(range(labels_no)),ind).tolist()
            for i in ind_lbl:
                d[str(i) + '.' + str(lbl[i])] = None
        if x_no > total_no:
            ind_x = np.delete(np.array(range(x_no)),ind).tolist()
            for i in ind_x:
                d[str(i) + '.'] = x[i]
        return d


def sort_dict(d):
    return OrderedDict(sorted(d.items(), key=lambda t: t[0]))


def dicts_of_lists(dictionary, n=1):
    for key, value in dictionary.iteritems():
        dictionary[key] = ensure_list(dictionary[key])
        if len(dictionary[key]) == 1 and n > 1:
            dictionary[key] = dictionary[key] * n
    return dictionary


def list_or_tuple_to_dict(obj):
    d = OrderedDict()
    for ind, value in enumerate(obj):
        d[str(ind)] = value
    return d


def dict_to_list_or_tuple(dictionary, output_obj="list"):
    dictionary = sort_dict(dictionary)
    output = dictionary.values()
    if output_obj == "tuple":
        output = tuple(output)
    return output


def list_of_dicts_to_dicts_of_ndarrays(lst):
    d = dict(zip(lst[0], zip(*list([d.values() for d in lst]))))
    for key, val in d.iteritems():
        d[key] = np.squeeze(np.stack(d[key]))
    return d


def arrays_of_dicts_to_dicts_of_ndarrays(arr):
    lst = arr.flatten().tolist()
    d = list_of_dicts_to_dicts_of_ndarrays(lst)
    for key, val in d.iteritems():
        d[key] = np.reshape(d[key], arr.shape)
    return d


def dicts_of_lists_to_lists_of_dicts(dictionary):
    return [dict(zip(dictionary,t)) for t in zip(*dictionary.values())]


def ensure_list(arg):
    if not (isinstance(arg, list)):
        try: #if iterable
            arg = list(arg)
        except: #if not iterable
            arg = [arg]
    return arg


def set_list_item_by_reference_safely(ind, item, lst):
    while ind >= len(lst):
        lst.append(None)
    lst.__setitem__(ind, item)


def get_list_or_tuple_item_safely(obj, key):
    try:
        return obj[int(key)]
    except:
        return None


def linear_index_to_coordinate_tuples(linear_index, shape):
    if len(linear_index) > 0:
        coordinates_tuple = np.unravel_index(linear_index, shape)
        return zip(*[ca.flatten().tolist() for ca in coordinates_tuple])
    else:
        return []


# This function is meant to confirm that two objects assumingly of the same type are equal, i.e., identical
def assert_equal_objects(obj1, obj2, attributes_dict=None, logger=None):

    def print_not_equal_message(attr, logger):
        # logger.error("\n\nValueError: Original and read object field "+ attr + " not equal!")
        # raise_value_error("\n\nOriginal and read object field " + attr + " not equal!")
        warning("Original and read object field " + attr + " not equal!", logger)

    if isinstance(obj1, dict):
        get_field1 = lambda obj, key: obj[key]
        if not (isinstance(attributes_dict, dict)):
            attributes_dict = dict()
            for key in obj1.keys():
                attributes_dict.update({key: key})
    else:
        get_field1 = lambda obj, attribute: getattr(obj, attribute)
        if not (isinstance(attributes_dict, dict)):
            attributes_dict = dict()
            for key in obj1.__dict__.keys():
                attributes_dict.update({key: key})
    if isinstance(obj2, dict):
        get_field2 = lambda obj, key: obj.get(key, None)
    else:
        get_field2 = lambda obj, attribute: getattr(obj, attribute, None)

    equal = True
    for attribute in attributes_dict:
        # print attributes_dict[attribute]
        field1 = get_field1(obj1, attributes_dict[attribute])
        field2 = get_field2(obj2, attributes_dict[attribute])
        try:
            # TODO: a better hack for the stupid case of an ndarray of a string, such as model.zmode or pmode
            # For non numeric types
            if isinstance(field1, basestring) or isinstance(field1, list) or isinstance(field1, dict) \
                    or (isinstance(field1, np.ndarray) and field1.dtype.kind in 'OSU'):
                if np.any(field1 != field2):
                    print_not_equal_message(attributes_dict[attribute], logger)
                    equal = False
            # For numeric numpy arrays:
            elif isinstance(field1, np.ndarray) and not field1.dtype.kind in 'OSU':
                # TODO: handle better accuracy differences, empty matrices and complex numbers...
                if field1.shape != field2.shape:
                    print_not_equal_message(attributes_dict[attribute], logger)
                    equal = False
                elif np.any(np.float32(field1) - np.float32(field2) > 0):
                    print_not_equal_message(attributes_dict[attribute], logger)
                    equal = False
            # For numeric scalar types
            elif isinstance(field1, (int, float, long, complex, np.number)):
                if np.float32(field1) - np.float32(field2) > 0:
                    print_not_equal_message(attributes_dict[attribute], logger)
                    equal = False
            else:
                warning("Comparing str(objects) for field "
                        + attributes_dict[attribute] + " because it is of unknown type!", logger)
                if np.any(str(field1) != str(field2)):
                    print_not_equal_message(attributes_dict[attribute], logger)
                    equal = False
        except:
            try:
                warning("Comparing str(objects) for field "
                        + attributes_dict[attribute] + " because there was an error!", logger)
                if np.any(str(field1) != str(field2)):
                    print_not_equal_message(attributes_dict[attribute], logger)
                    equal = False
            except:
                raise_value_error("ValueError: Something went wrong when trying to compare "
                                  + attributes_dict[attribute] + " !", logger)

    if equal:
        return True
    else:
        return False

def shape_to_size(shape):
    shape = np.array(shape)
    shape = shape[shape > 0]
    return shape.prod()


def assert_arrays(params, shape=None, transpose=False):
    # type: (object, object) -> object
    if shape is None or \
        not(isinstance(shape, tuple)
            and len(shape) in range(3) and np.all([isinstance(s, (int, np.int)) for s in shape])):
        shape = None
        shapes = [] # list of all unique shapes
        n_shapes = []   # list of all unique shapes' frequencies
        size = 0    # initial shape
    else:
        size = shape_to_size(shape)

    for ip in range(len(params)):
        # Convert all accepted types to np arrays:
        if isinstance(params[ip], np.ndarray):
            pass
        elif isinstance(params[ip], (list, tuple)):
            # assuming a list or tuple of symbols...
            params[ip] = np.array(params[ip]).astype(type(params[ip][0]))
        elif isinstance(params[ip], (float, int, long, complex, np.number)):
            params[ip] = np.array(params[ip])
        else:
            try:
                import sympy
            except:
                raise_import_error("sympy import failed")
            if isinstance(params[ip], tuple(sympy.core.all_classes)):
                params[ip] = np.array(params[ip])
            else:
                raise_value_error("Input " + str(params[ip]) + " of type " + str(type(params[ip])) + " is not numeric, "
                                                                                  "of type np.ndarray, nor Symbol")
        if shape is None:
            # Only one size > 1 is acceptable
            if params[ip].size != size:
                if size > 1 and params[ip].size > 1:
                    raise_value_error("Inputs are of at least two distinct sizes > 1")
                elif params[ip].size > size:
                    size = params[ip].size
            # Construct a kind of histogram of all different shapes of the inputs:
            ind = np.array([(x == params[ip].shape) for x in shapes])
            if np.any(ind):
                ind = np.where(ind)[0]
                #TODO: handle this properly
                n_shapes[int(ind)] += 1
            else:
                shapes.append(params[ip].shape)
                n_shapes.append(1)
        else:
            if params[ip].size > size:
                raise_value_error("At least one input is of a greater size than the one given!")

    if shape is None:
        # Keep only shapes of the correct size
        ind = np.array([shape_to_size(s) == size for s in shapes])
        shapes = np.array(shapes)[ind]
        n_shapes = np.array(n_shapes)[ind]
        # Find the most frequent shape
        ind = np.argmax(n_shapes)
        shape = tuple(shapes[ind])

    if transpose and len(shape) > 1:
        if (transpose is "horizontal" or "row" and shape[0] > shape[1]) or \
           (transpose is "vertical" or "column" and shape[0] < shape[1]):
            shape = list(shape)
            temp = shape[1]
            shape[1] = shape[0]
            shape[0] = temp
            shape = tuple(shape)

    # Now reshape or tile when necessary
    for ip in range(len(params)):
        try:
            if params[ip].shape != shape:
                if params[ip].size in [0, 1]:
                    params[ip] = np.tile(params[ip], shape)
                else:
                    params[ip] = np.reshape(params[ip], shape)
        except:
            print("\n\nwhat the fuck??")

    if len(params) == 1:
        return params[0]
    else:
        return tuple(params)


def make_float(x):
    if isinstance(x, np.ndarray):
        return x.astype("f")
    else:
        return np.float(x)


def make_int(x):
    if isinstance(x, np.ndarray):
        return x.astype("i")
    else:
        return np.int(x)


def parcellation_correspondance(inds_from, labels_from, labels_to):
    inds_to = []
    for ind in inds_from:
        lbl = labels_from[ind]
        inds_to.append(np.where(labels_to == lbl)[0][0])
    if len(inds_to) != 1:
        return inds_to
    else:
        return inds_to[0]

