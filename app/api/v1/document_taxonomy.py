from fastapi import APIRouter

from app.core.document_taxonomy import list_document_taxonomy
from app.schemas.document_taxonomy import (
    DocumentTaxonomyGroupRead,
    DocumentTaxonomyResponse,
    DocumentTaxonomyTypeRead,
)

router = APIRouter()


@router.get("/document-taxonomy", response_model=DocumentTaxonomyResponse)
def get_document_taxonomy() -> DocumentTaxonomyResponse:
    return DocumentTaxonomyResponse(
        data=[
            DocumentTaxonomyGroupRead(
                code=group.code,
                label=group.label,
                description=group.description,
                types=[
                    DocumentTaxonomyTypeRead(
                        code=document_type.code,
                        label=document_type.label,
                        description=document_type.description,
                    )
                    for document_type in group.types
                ],
            )
            for group in list_document_taxonomy()
        ]
    )
