```python
def create_decision_tree(data, attributes, class_attr, fitness_func, wrapper, **kwargs):
    """
    Returns a new decision tree based on the examples given.
    Args:
        data: first batch data, to determine attribute distribute.
        attributes:
        class_attr:
        fitness_func:
        wrapper: pass Class Tree to record all of parameter in trees.
    """
    
    split_attr = kwargs.get('split_attr', None)
    split_val = kwargs.get('split_val', None)
    
    assert class_attr not in attributes, "Class attributes should not in class attribute"
    node = None
    data = list(data) if isinstance(data, Data) else data
    # [to change]不需要因为方差阈值或者所有数据都是同一个标签而停止划分，我们停止划分的标准应该是当前网络的深度，当前节点被作为叶节点
    if wrapper.is_continuous_class:
        stop_value = CDist(seq=[r[class_attr] for r in data])
        # For a continuous class case, stop if all the remaining records have
        # a variance below the given threshold.
        stop = wrapper.leaf_threshold is not None \
            and stop_value.variance <= wrapper.leaf_threshold
    else:
        stop_value = DDist(seq=[r[class_attr] for r in data])
        # For a discrete class, stop if all remaining records have the same
        # classification.
        stop = len(stop_value.counts) <= 1
	# ---------
    
    if not data or len(attributes) <= 0:
        # If the dataset is empty or the attributes list is empty, return the
        # default value. The target attribute is not in the attributes list, so
        # we need not subtract 1 to account for the target attribute.
        if wrapper:
            wrapper.leaf_count += 1
        return stop_value
    elif stop:
        # If all the records in the dataset have the same classification,
        # return that classification.
        if wrapper:
            wrapper.leaf_count += 1
        return stop_value
    else:
        #[to change] random select next attribute
        # Choose the next best attribute to best classify our data
        best = choose_attribute(
            data,
            attributes,
            class_attr,
            fitness_func,
            method=wrapper.metric)

        # Create a new decision tree/node with the best attribute and an empty
        # dictionary object--we'll fill that up next.
		# tree = {best:{}}
        node = Node(tree=wrapper, attr_name=best)
        node.n += len(data)

        # Create a new decision tree/sub-node for each of the values in the
        # best attribute field
        for val in get_values(data, best):
            # Create a subtree for the current value under the "best" field
            # [question] for countinus attribute, should we regard it as discrete points. means create a node for each points?
            subtree = create_decision_tree(
                [r for r in data if r[best] == val],
                [attr for attr in attributes if attr != best],
                class_attr,
                fitness_func,
                split_attr=best,
                split_val=val,
                wrapper=wrapper)

            # Add the new subtree to the empty dictionary object in our new
            # tree/node we just created.
            if isinstance(subtree, Node):
                node._branches[val] = subtree
            elif isinstance(subtree, (CDist, DDist)):
                node.set_leaf_dist(attr_value=val, dist=subtree)
                # [to change]这里找到了叶子节点，我们需要把这些节点额外的串起来，放在另外一个数据结构中，方便最后的神经网络的统一训练
                # 节点要记录，当前节点的所有已经选择的统一特征
            else:
                raise Exception("Unknown subtree type: %s" % (type(subtree),))

    return node
```



```python
    def distribution(self, record, depth=0):
        """
        Returns the estimated value of the class attribute for the given
        record.
        change from predict
        """
        
        # Check if we're ready to predict.
        if not self.ready_to_predict:
            raise NodeNotReadyToPredict
        
        # Lookup attribute value.
        attr_value = self._get_attribute_value_for_node(record)
        
        # Propagate decision to leaf node.
        if self.attr_name:
            if attr_value in self._branches:
                try:
                    return self._branches[attr_value].predict(record, depth=depth+1)
                except NodeNotReadyToPredict:
                    #TODO:allow re-raise if user doesn't want an intermediate prediction?
                    pass
        # [to change] 找到节点之后，把当前的数据绑定到对应的节点中
 		# 我们需要把这个数据的下标绑定到节点内部，方便最后神经网络的训练
        # Otherwise make decision at current node.
        # ------[delete]-----
        if self.attr_name:
            if self._tree.data.is_continuous_class:
                return self._attr_value_cdist[self.attr_name][attr_value].copy()
            else:
				# return self._class_ddist.copy()
                return self.get_value_ddist(self.attr_name, attr_value)
        elif self._tree.data.is_continuous_class:
            # Make decision at current node, which may be a true leaf node
            # or an incomplete branch in a tree currently being built.
            assert self._class_cdist is not None
            return self._class_cdist.copy()
        else:
            return self._class_ddist.copy()
        # ------[delete]-----
```



```python
def Incremental_Training_Driver(self,Node,Data):
    for leaf in self.leaves:
        attrs = Node.common_attrs
        leaf_data = Data[leaf.data_indexes][ALL_ATTR - attrs]
        leaf.nn_model.train(leaf_data)
        leaf.data_indexes = empty
```



```python
    def predict(self, record, depth=0):
        """
        Returns the estimated value of the class attribute for the given
        record.
        """
        
        # Check if we're ready to predict.
        if not self.ready_to_predict:
            raise NodeNotReadyToPredict
        
        # Lookup attribute value.
        attr_value = self._get_attribute_value_for_node(record)
        
        # Propagate decision to leaf node.
        if self.attr_name:
            if attr_value in self._branches:
                try:
                    return self._branches[attr_value].predict(record, depth=depth+1)
                except NodeNotReadyToPredict:
                    #TODO:allow re-raise if user doesn't want an intermediate prediction?
                    pass
                
        # Otherwise make decision at current node.
        if self.attr_name:
            # [to change] use nn to predict!
            # -----[delete]-----
            if self._tree.data.is_continuous_class:
                return self._attr_value_cdist[self.attr_name][attr_value].copy()
            else:
                # return self._class_ddist.copy()
                return self.get_value_ddist(self.attr_name, attr_value)
            # -----[delete]-----
        elif self._tree.data.is_continuous_class:
            # Make decision at current node, which may be a true leaf node
            # or an incomplete branch in a tree currently being built.
            assert self._class_cdist is not None
            return self._class_cdist.copy()
        else:
            return self._class_ddist.copy()
```



需要修改的数据结构

1. node：
   1. 需要绑定当前节点的拥有的数据
   2. 需要记录当前节点的普遍特征，模型训练的时候删除这些特征
   3. 需要绑定一个神经网络模型，在神经网络中进行训练


todo

当前的代码，是不能支持数据集中有离散属性的，我需要解决这个问题

```python
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
        assert matches, "Invalid header element: %s" % (el,)
        el_name, el_type, el_mode = matches[0]
        logging.info(matches[0])
        el_name = el_name.strip()
        self.header_order.append(el_name)
        self.header_types[el_name] = el_type
        if el_mode == ATTR_MODE_CLASS:

            assert self._class_attr_name is None, \
                "Multiple class attributes are not supported."
            self._class_attr_name = el_name
        else:
            # [todo]to support continuous attributes
            assert self.header_types[el_name] != ATTR_TYPE_CONTINUOUS, \
                "Non-class continuous attributes are not supported."
    assert self._class_attr_name, "A class attribute must be specified."
```
相关板块：

- node._get_attribute_value_for_node



源代码有很多重复计算的模块，应该删掉，一次计算就备份起来！

- unique,每次需要遍历一整个数据集，删掉

源项目的决策树没法适应连续属性，需要加上这个功能



空属性问题：

理论上讲，我们应该随机划分到某一个深度之后停止划分



max和min的取值现在直接来自第一批数据，实际上应该手动标定



对于连续属性，我们简单的二分会不会效果不太好？是不是可以考虑增加分支数



树的规模会不会太大？



热启动效果不是特别好



目前数据还不能适应回归问题，需要解决



对于大量特征而言，单单5层的决策树，有什么意义呢？





1. 数据预处理
2. ​