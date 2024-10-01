@dataclass(frozen=True)
class AreaDifferentFromJDex:
    """An area with a differently-named JDex entry."""

    area: str
    jdex_name: str
    type: Literal["AREA_DIFFERENT_FROM_JDEX"] = "AREA_DIFFERENT_FROM_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [JDex name: {self.jdex_name}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An area was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class AreaNotInJDex:
    """An area without a corresponding JDex entry."""

    area: str
    type: Literal["AREA_NOT_IN_JDEX"] = "AREA_NOT_IN_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [area {_print_area(self.area)}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An area was found in your files that is missing from your JDex.",
            fix="Go add a corresponding entry to your JDex, or delete this if it's unused.",
        )


@dataclass(frozen=True)
class CategoryDifferentFromJDex:
    """A category with a differently-named JDex entry."""

    category: str
    jdex_name: str
    type: Literal["CATEGORY_DIFFERENT_FROM_JDEX"] = "CATEGORY_DIFFERENT_FROM_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [JDex name: {self.jdex_name}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A category was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class CategoryInWrongArea:
    """A category that, by its number, has been put in the wrong area."""

    cat_area: str
    actual_area: str
    type: Literal["CATEGORY_IN_WRONG_AREA"] = "CATEGORY_IN_WRONG_AREA"

    def display(self, files: list[File]) -> str:
        """Given the file's name, print the error message for it."""
        return f"{_print_nest(files[0])} [in {_print_area(self.actual_area)} but should be in {_print_area(self.cat_area)}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some categories are in the wrong area.",
            fix="Move them into the correct area folder.",
        )
