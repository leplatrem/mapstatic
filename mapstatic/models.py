import datetime
import re

from pydantic import BaseModel, validator


class Element(BaseModel):
    """
    """
    slug: str
    title: str
    datetime: datetime.datetime
    tags: list[str]

    geometries: dict
    description: str

    @validator("tags", pre=True)
    def split_tags(cls, value):
        split = [t.strip() for t in re.split(",| ", value)]
        return split

    class Config:
        arbitrary_types_allowed = True
