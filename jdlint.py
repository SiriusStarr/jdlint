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
        return f"{_print_nest(files[0])} [area: {_print_area(self.area)}]"

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


@dataclass(frozen=True)
class CategoryNotInJDex:
    """An category without a corresponding JDex entry."""

    category: str
    type: Literal["CATEGORY_NOT_IN_JDEX"] = "CATEGORY_NOT_IN_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [category: {self.category}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A category was found in the files that is missing from the JDex.",
            fix="Go add a corresponding entry to your JDex.",
        )


@dataclass(frozen=True)
class DuplicateArea:
    """An area that has been used multiple times."""

    area: str
    type: Literal["DUPLICATE_AREA"] = "DUPLICATE_AREA"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"Area {_print_area(self.area)}:\n    " + "\n    ".join(
            [_print_nest(f) for f in files]
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate areas were used.",
            fix="Assign a new area to one of them.",
        )


@dataclass(frozen=True)
class DuplicateCategory:
    """A category that has been used multiple times."""

    category: str
    type: Literal["DUPLICATE_CATEGORY"] = "DUPLICATE_CATEGORY"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"Category {self.category}:\n    " + "\n    ".join(
            [_print_nest(f) for f in files]
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate categorys were used.",
            fix="Assign a new category to one of them.",
        )


@dataclass(frozen=True)
class DuplicateId:
    """An ID that has been used multiple times."""

    id: str
    type: Literal["DUPLICATE_ID"] = "DUPLICATE_ID"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"ID {self.id}:\n    " + "\n    ".join([_print_nest(f) for f in files])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate IDs were used.",
            fix="Assign a new ID to one of them.",
        )


@dataclass(frozen=True)
class FileOutsideId:
    """A file was encountered not in a terminal ID folder."""

    type: Literal["FILE_OUTSIDE_ID"] = "FILE_OUTSIDE_ID"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files were found outside of IDs.",
            fix="Files should only be kept in IDs and not higher in the hierarchy.",
        )
