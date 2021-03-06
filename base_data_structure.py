#!/usr/bin/env python
# coding=utf-8

# Author      :   Xionghui Chen
# Created     :   2017.6.23
# Modified    :   2017.6.23
# Version     :   1.0
import os
import csv
from collections import defaultdict

from six import iteritems, iterkeys, itervalues, string_types


from global_function_constant import *

class CDist(object):
    """
    Incrementally tracks the probability distribution of continuous numbers.
    """
    
    def __init__(self, seq=None, mean=None, var=None, stdev=None):
        self.clear()
        if mean is not None:
            self.mean_sum = mean
            self.mean_count = 1
        if var is not None:
            self.last_variance = var
            self.mean_count = 1
        if stdev is not None:
            self.last_variance = stdev**2
            self.mean_count = 1
        if seq:
            for n in seq:
                self += n
    
    def clear(self):
        self.mean_sum = 0
        self.mean_count = 0
        self.last_variance = 0
    
    def copy(self):
        return copy.deepcopy(self)
    
    def __repr__(self):
        return "<%s mean=%s variance=%s>" \
            % (type(self).__name__, self.mean, self.variance)
    
    def __iadd__(self, value):
        last_mean = self.mean
        self.mean_sum += value
        self.mean_count += 1
        if last_mean is not None:
            self.last_variance = self.last_variance \
                + (value  - last_mean)*(value - self.mean)
        return self
    
    @property
    def count(self):
        """
        The total number of samples forming this distribution.
        """
        return self.mean_count
        
    @property
    def mean(self):
        if self.mean_count:
            return self.mean_sum/float(self.mean_count)
    
    @property
    def variance(self):
        if self.mean_count:
            return self.last_variance/float(self.mean_count)
        
    @property
    def standard_deviation(self):
        var = self.variance
        if var is None:
            return
        return math.sqrt(var)
    
    def probability_lt(self, x):
        """
        Returns the probability of a random variable being less than the
        given value.
        """
        if self.mean is None:
            return
        return normdist(x=x, mu=self.mean, sigma=self.standard_deviation)
    
    def probability_in(self, a, b):
        """
        Returns the probability of a random variable falling between the given
        values.
        """
        if self.mean is None:
            return
        p1 = normdist(x=a, mu=self.mean, sigma=self.standard_deviation)
        p2 = normdist(x=b, mu=self.mean, sigma=self.standard_deviation)
        return abs(p1 - p2)
    
    def probability_gt(self, x):
        """
        Returns the probability of a random variable being greater than the
        given value.
        """
        if self.mean is None:
            return
        p = normdist(x=x, mu=self.mean, sigma=self.standard_deviation)
        return 1-p


class DDist(object):
    """
    Incrementally tracks the probability distribution of discrete elements.
    """    
    def __init__(self, seq=None):
        self.clear()
        if seq:
            for k in seq:
                self.counts[k] += 1
                self.total += 1
    
    def __cmp__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return cmp(
            (frozenset(self.counts.items()), self.total),
            (frozenset(other.counts.items()), other.total)
        )
    
    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return (frozenset(self.counts.items()), self.total) == \
            (frozenset(other.counts.items()), other.total)
    
    def __getitem__(self, k):
        """
        Returns the probability for the given element.
        """
        cnt = 0
        if k in self.counts:
            cnt = self.counts[k]
        return cnt/float(self.total)
    
    def __hash__(self):
        return hash((frozenset(self.counts.items()), self.total))
    
    def __repr__(self):
        s = []
        for k, prob in self.probs:
            s.append("%s=%s" % (k, prob))
        return "<%s %s>" % (type(self).__name__, ', '.join(s))
    
    def add(self, k, count=1):
        """
        Increments the count for the given element.
        """
        self.counts[k] += count
        self.total += count
    
    @property
    def best(self):
        """
        Returns the element with the highest probability.
        """
        b = (-1e999999, None)
        for k, c in iteritems(self.counts):
            b = max(b, (c, k))
        return b[1]
    
    @property
    def best_prob(self):
        probs = self.probs
        if not probs:
            return
        best = -1e999999
        for _, prob in probs:
            best = max(best, prob)
        return best
    
    def clear(self):
        self.counts = defaultdict(int)
        self.total = 0
    
    def copy(self):
        return copy.deepcopy(self)
    
    @property
    def count(self):
        """
        The total number of samples forming this distribution.
        """
        return self.total
    
    def keys(self):
        return self.counts.keys()
    
    @property
    def probs(self):
        """
        Returns a list of probabilities for all elements in the form
        [(value1,prob1),(value2,prob2),...].
        """
        return [
            (k, self.counts[k]/float(self.total))
            for k in iterkeys(self.counts)
        ]
    
    def update(self, dist):
        """
        Adds the given distribution's counts to the current distribution.
        """
        assert isinstance(dist, DDist)
        for k, c in iteritems(dist.counts):
            self.counts[k] += c
        self.total += dist.total

class Data(object):
    """
    Parses, validates and iterates over tabular data in a file
    or an generic iterator.
    
    This does not store the actual data rows. It only stores the row schema.
    """
    
    def __init__(self, inp, order=None, types=None, modes=None):
        """
            inp: path name
                data format:
                    a:discrete,b:discrete,c:discrete,d:discrete,cls:nominal:class
                    1,1,1,1,a
                    1,1,1,2,a
                    1,1,2,3,a
                    1,1,2,4,a
                    1,2,3,5,a
                    1,2,6,6,a
                    1,2,4,7,a
                    1,3,5,8,a
                    2,2,4,1,b
                    2,3,5,2,b
                    2,3,3,3,b
                    2,3,6,4,b
                    2,4,7,5,b
                    2,4,7,6,b
                    2,4,8,7,b
                    2,4,8,8,b
        """
        
        self.header_types = types or {} # {attr_name:type}
        self.header_modes = modes or {} # {attr_name:mode}
        if isinstance(order, string_types):
            order = order.split(',')
        self.header_order = order or [] # [attr_name,...]

        # Validate header type.
        if isinstance(self.header_types, (tuple, list)):
            assert self.header_order, 'If header type names were not ' + \
                'given, an explicit order must be specified.'
            assert len(self.header_types) == len(self.header_order), \
                'Header order length must match header type length.'
            self.header_types = dict(zip(self.header_order, self.header_types))
        
        self.filename = None
        self.data = None
        if isinstance(inp, string_types):
            filename = inp
            assert os.path.isfile(filename), \
                "File \"%s\" does not exist." % filename
            self.filename = filename
        else:
            assert self.header_types, "No attribute types specified."
            assert self.header_modes, "No attribute modes specified."
            # assert self.header_order, "No attribute order specified."
            self.data = inp
        
        self._class_attr_name = None
        if self.header_modes:
            for k, v in iteritems(self.header_modes):
                if v != CLS:
                    continue
                self._class_attr_name = k
                break
            assert self._class_attr_name, "No class attribute specified."

        # store unique value of attributes in data.
        # eg. {'f1':[1,2,3,4],'f2':[4,5,6,7]}
        self._uni_attri_value = {} 
        # store unique value of class label
        # eg. [1,2,3,4,5]
        self._uni_class_value = set()
        self._extre_attri_value = {}


    @property
    def uni_attri_value(self):
        if self._uni_attri_value == {}:
            attrs = self.attribute_names
            for item in self:
                for key in attrs:
                    if not self._uni_attri_value.has_key(key):
                        self._uni_attri_value[key] = set()
                    self._uni_attri_value[key].add(item[key])
        return self._uni_attri_value

    @property
    def uni_class_value(self):
        if self._uni_class_value ==set():
            class_name = self.class_attribute_name
            for item in self:
                self._uni_class_value.add(item[class_name])
        return self._uni_class_value

    @property
    def extre_attri_value(self):
        if self._extre_attri_value == {}:
            for key,item in self.uni_attri_value.items():
                self._extre_attri_value[key] = [min(item),max(item)]
        return self._extre_attri_value   



    def copy_no_data(self):
        """
        Returns a copy of the object without any data.
        """
        return type(self)(
            [],
            order=list(self.header_modes),
            types=self.header_types.copy(),
            modes=self.header_modes.copy())
    
    def __len__(self):
        if self.filename:
            return max(0, open(self.filename).read().strip().count('\n'))
        elif hasattr(self.data, '__len__'):
            return len(self.data)

    def __bool__(self):
        return bool(len(self))
    __nonzero__ = __bool__

    @property
    def class_attribute_name(self):
        return self._class_attr_name

    @property
    def attribute_names(self):
        self._read_header()
        return [
            n for n in iterkeys(self.header_types)
            if n != self._class_attr_name
        ]



    def get_attribute_type(self, name):
        if not self.header_types:
            self._read_header()
        return self.header_types[name]

    @property
    def is_continuous_class(self):
        self._read_header()
        return self.get_attribute_type(self._class_attr_name) \
            == ATTR_TYPE_CONTINUOUS

    def is_valid(self, name, value):
        """
        Returns true if the given value matches the type for the given name
        according to the schema.
        Returns false otherwise.
        """
        if name not in self.header_types:
            return False
        t = self.header_types[name]
        if t == ATTR_TYPE_DISCRETE:
            return isinstance(value, int)
        elif t == ATTR_TYPE_CONTINUOUS:
            return isinstance(value, (float, Decimal))
        return True

    def _read_header(self):
        """
        When a CSV file is given, extracts header information the file.
        Otherwise, this header data must be explicitly given when the object
        is instantiated.
        """
        if not self.filename or self.header_types:
            return
        rows = csv.reader(open(self.filename))
        #header = rows.next()
        header = next(rows)
        self.header_types = {} # {attr_name:type}
        self._class_attr_name = None
        self.header_order = [] # [attr_name,...]
        for el in header:
            matches = ATTR_HEADER_PATTERN.findall(el)
            # logging.info("match is %s"%matches)
            assert matches, "Invalid header element: %s" % (el,)
            el_name, el_type, el_mode = matches[0]
            # logging.info(matches[0])
            el_name = el_name.strip()
            self.header_order.append(el_name)
            self.header_types[el_name] = el_type
            if el_mode == ATTR_MODE_CLASS:

                assert self._class_attr_name is None, \
                    "Multiple class attributes are not supported."
                self._class_attr_name = el_name
            else:
                # [todo]to support continuous attributes
                # assert self.header_types[el_name] != ATTR_TYPE_CONTINUOUS, \
                #     "Non-class continuous attributes are not supported."
                pass
        assert self._class_attr_name, "A class attribute must be specified."

    def validate_row(self, row):
        """
        Ensure each element in the row matches the schema.
        """
        clean_row = {}
        if isinstance(row, (tuple, list)):
            assert self.header_order, "No attribute order specified."
            assert len(row) == len(self.header_order), \
                "Row length does not match header length."
            itr = zip(self.header_order, row)
        else:
            assert isinstance(row, dict)
            itr = iteritems(row)
        # logging.error(itr)
        for el_name, el_value in itr:
            if self.header_types[el_name] == ATTR_TYPE_DISCRETE:
                clean_row[el_name] = int(el_value)
            elif self.header_types[el_name] == ATTR_TYPE_CONTINUOUS:
                clean_row[el_name] = float(el_value)
            elif self.header_types[el_name] == ATTR_TYPE_NOMINAL:
                assert el_value.isdigit(),"you should transform nominal type into number instead of raw string."
                clean_row[el_name] = int(el_value)
        return clean_row

    def _get_iterator(self):
        if self.filename:
            self._read_header()
            itr = csv.reader(open(self.filename))
            next(itr) # Skip header.
            return itr
        return self.data

    def __iter__(self):
        for row in self._get_iterator():
            if not row:
                continue
            yield self.validate_row(row)
            
    def split(self, ratio=0.5, leave_one_out=False):
        """
        Returns two Data instances, containing the data randomly split between
        the two according to the given ratio.
        
        The first instance will contain the ratio of data specified.
        The second instance will contain the remaining ratio of data.
        
        If leave_one_out is True, the ratio will be ignored and the first
        instance will contain exactly one record for each class label, and
        the second instance will contain all remaining data.
        """
        a_labels = set()
        a = self.copy_no_data()
        b = self.copy_no_data()
        for row in self:
            if leave_one_out and not self.is_continuous_class:
                label = row[self.class_attribute_name]
                if label not in a_labels:
                    a_labels.add(label)
                    a.data.append(row)
                else:
                    b.data.append(row)
            elif not a:
                a.data.append(row)
            elif not b:
                b.data.append(row)
            elif random.random() <= ratio:
                a.data.append(row)
            else:
                b.data.append(row)
        return a, b