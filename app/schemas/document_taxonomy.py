from pydantic import BaseModel


class DocumentTaxonomyTypeRead(BaseModel):
    code: str
    label: str
    description: str


class DocumentTaxonomyGroupRead(BaseModel):
    code: str
    label: str
    description: str
    types: list[DocumentTaxonomyTypeRead]


class DocumentTaxonomyResponse(BaseModel):
    data: list[DocumentTaxonomyGroupRead]
