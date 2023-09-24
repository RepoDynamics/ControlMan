import re

class _DictFiller:

    def __init__(self, templated_data: dict | list | str | bool | int | float, metadata: dict):
        self._data = templated_data
        self._meta = metadata
        return

    def fill(self):
        return self._recursive_subst(self._data)

    def _recursive_subst(self, value):
        if isinstance(value, str):
            match_whole_str = re.match(r"^\${{([^{}]+)}}$", value)
            if match_whole_str:
                return self._substitute_val(match_whole_str.group(1))
            return re.sub(r"{{{(.*?)}}}", lambda x: str(self._substitute_val(x.group(1))), value)
        if isinstance(value, list):
            for idx, elem in enumerate(value):
                value[idx] = self._recursive_subst(elem)
        elif isinstance(value, dict):
            for key, val in value.items():
                key_filled = self._recursive_subst(key)
                if key_filled == key:
                    value[key] = self._recursive_subst(val)
                else:
                    value[key_filled] = self._recursive_subst(value.pop(key))
        return value

    def _substitute_val(self, match):

        def recursive_retrieve(obj, address):
            if len(address) == 0:
                return obj
            curr_add = address.pop(0)
            try:
                next_layer = obj[curr_add]
            except (TypeError, KeyError, IndexError) as e:
                try:
                    next_layer = self._recursive_subst(obj)[curr_add]
                except (TypeError, KeyError, IndexError) as e2:
                    raise KeyError(f"Object '{obj}' has no element '{curr_add}'") from e
            return recursive_retrieve(next_layer, address)

        parsed_address = []
        for add in match.strip().split("."):
            name = re.match(r"^([^[]+)", add).group()
            indices = re.findall(r"\[([^]]+)]", add)
            parsed_address.append(name)
            parsed_ind = []
            for idx in indices:
                if ":" not in idx:
                    parsed_ind.append(int(idx))
                else:
                    slice_ = [int(i) if i else None for i in idx.split(":")]
                    parsed_ind.append(slice(*slice_))
            parsed_address.extend(parsed_ind)
        return recursive_retrieve(self._data, address=parsed_address)


def fill(templated_data: dict | list | str | bool | int | float, metadata: dict):
    return _DictFiller(templated_data=templated_data, metadata=metadata).fill()
