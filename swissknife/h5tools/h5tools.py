# Functions to do stuff with h5 open files
import logging
import h5py

logger = logging.getLogger('h5tools')


def h5_decorator(leave_open=True, default_mode='r'):
    """
    Decorator to open h5 structure if the path was provided to a function.
    :param h5_function: a function that receives an h5file as first argument
    :param leave_open: whether to leave the file open.
        It is overriden when file is entered open
    :param default_mode: what mode to open the file by default.
        It is overriden when file is entered open and when option 'mode' is set
        in h5_function (if it exists)
    :return: decorated function that takes open or path as first argument
    """
    def wrap(h5_function):
        def file_checker(h5_file, *args, **kwargs):
            if 'mode' in kwargs.keys():
                mode = kwargs['mode']
            else:
                mode = default_mode
            # logger.debug('leave open {}'.format(leave_open))
            logger.debug('mode {}'.format(mode))
            try:
                if type(h5_file) is not h5py._hl.files.File:
                    if leave_open:
                        logging.debug('Opening H5 file: {}'.format(h5_file))
                        h5_file = h5py.File(h5_file, mode)
                        return_value = h5_function(h5_file, *args, **kwargs)
                    else:
                        with h5py.File(h5_file, mode) as h5_file:
                            return_value = h5_function(h5_file, *args, **kwargs)

                else:
                    return_value = h5_function(h5_file, *args, **kwargs)
                return return_value

            except UnboundLocalError as err:
                last_err = err
                logger.error(err)

        return file_checker
    return wrap


def list_subgroups(h5_group):
    """
    List the groups within a group, not recursively
    :param h5_group: a Group object
    :return: a list of the keys of items that are instances of group
    """
    return [key for key, val in h5_group.items() if isinstance(val, h5py.Group)]


def dict_2_attr_translator(item):
    """
    Translate a value from a dictionary to a valid value for an attribute
    :param item: value of a read item of a dict (not a dict)
    :return: value to store as attribute
    """
    if item is None:
        value = 'None'
    else:
        value = item

    return value


def dict_2_group(parent_group, dic, name, replace=False):
    """
    Recursively dumps a dictionary into a group.
    keys go to attributes, values go to attribute values.
    keys that correspond to dictionaries go to new groups, recursively
    :param parent_group: parent group
    :param dic: dictionary
    :param name: name for the new group
    :return:
    """
    # group parent group or path, dict dictionary, name name of new group
    logger.debug('Translating dictionary key {} into its own group'.format(name))
    try:
        group = parent_group.create_group(name)
    except ValueError as err:
        logger.debug(err)
        if 'Name already exists' in err.args[0]:
            if replace:
                logger.debug('Group {} already exists; replacing'.format(name))
                group = parent_group.require_group(name)
            else:
                logger.debug('Group {} already exists; skipping'.format(name))
                return

    for key, item in dic.items():
        if not isinstance(item, dict):
            try:
                item = dict_2_attr_translator(item)
                group.attrs.create(key, item)
            except ValueError:
                logger.info("Wrong type error for key {}, setting None".format(type(item)))
                group.attrs.create(key, None)
        else:
            dict_2_group(group, item, key)


def attr_2_dict_translator(value):
    """
    :param value: value of an attribute
    :return: out_value for a dictionary
    """
    if type(value) is str and value == 'None':
        out_value = None
    else:
        out_value = value
    return out_value


def obj_attrs_2_dict_translator(h5obj):
    dic = {}
    for attr, value in h5obj.attrs.items():
        try:
            # logger.debug('attr {}'.format(attr))
            dic[attr] = attr_2_dict_translator(value)
        except ValueError:
            logger.warning("Could not translate value for attribute {}".format(attr))
            dic[attr] = None
    return dic


def group_2_dict(parent_dic, group, key_name):
    """
    Recursively dumps a group into a dictionary.
    attributes go to keys, values go to item values.
    subgroups to new dictionaries, recursively
    :param parent_dic: parent dictionary where to
    :param group: group to translate
    :param key_name: key of the dictionary to create for this group
    :return:
    """
    # enter a group with the attributes and lay it in a dictionary as key 'key_name'
    logger.debug('Translating group {} into its own dictionary'.format(key_name))
    parent_dic[key_name] = dict()
    dic = parent_dic[key_name]
    for attr, value in group.attrs.items():
        try:
            # logger.debug('attr {}'.format(attr))
            dic[attr] = attr_2_dict_translator(value)
        except ValueError:
            logger.warning("Could not translate value for attribute {}".format(attr))
            dic[attr] = None

    for subgroup_name, subgroup_obj in group.items():
        logger.debug('Subgroup {}'.format(subgroup_name))
        try:
            assert(isinstance(subgroup_obj, h5py.Group))
            # logger.info('Ok subgroup {}'.format(subgroup_name))
            group_2_dict(dic, subgroup_obj, subgroup_name)
        except AssertionError:
            try:
                assert (isinstance(subgroup_obj, h5py.Dataset))
                # logger.info('Ok dataset {}'.format(subgroup_name))
                dic[subgroup_name] = obj_attrs_2_dict_translator(subgroup_obj)
                # logger.info('Translated attrs of dataset {}'.format(subgroup_name))
            except:
                raise

    return parent_dic


def insert_table(group, table, name, attr_dict=None):
    dset = group.create_dataset(name, data=table)
    if attr_dict is not None:
        append_atrributes(dset, attr_dict)
    return dset


def insert_group(parent_group, name, attr_dict_list=None):
    new_group = parent_group.create_group(name)
    if attr_dict_list is not None:
        append_atrributes(new_group, attr_dict_list)
    return new_group


def append_atrributes(h5obj, attr_dict):
    """
    Write a dictionary (no recursion) as a list of attributes belonging to an h5 object (dataset/group)
    :param h5obj: Group or Dataset h5py object.
    :param attr_dict: Dictionary (with no dictionaries)
    :return:
    """
    for key, item in attr_dict.items():
        # print attr_dict['name'] + ' {0} - {1}'.format(attr_dict['data'], attr_dict['dtype'])
        if isinstance(key, dict):
            logger.warning('Skipping sub-dictionary {0} in appending attributes of {1}'.format(key, h5obj.name))
            item = 'Error'
        h5obj.attrs.create(key, dict_2_attr_translator(item))
