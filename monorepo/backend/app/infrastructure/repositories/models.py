"""Punto único de registro de los modelos de base de datos.

SQLModel solo agrega una tabla a `SQLModel.metadata` cuando su módulo se importa.
Alembic necesita ese metadata completo para `--autogenerate`: si falta un módulo,
no ve la tabla y genera una migración que la **borra**.

Importar desde acá evita que eso dependa de qué módulos haya cargado la
aplicación por casualidad. Al agregar un modelo nuevo, agregarlo también aquí.
"""

from app.infrastructure.repositories.deep_analysis_model import (
    DeepAnalysisModel,
)
from app.infrastructure.repositories.matching_result_model import (
    MatchingResultModel,
)
from app.infrastructure.repositories.notification_model import (
    NotificationDeliveryModel,
    NotificationModel,
    NotificationPreferenceModel,
)
from app.infrastructure.repositories.question_model import QuestionModel
from app.infrastructure.repositories.saved_tender_model import SavedTenderModel
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.tender_model import (
    BuyerInstitutionModel,
    RegionModel,
    TenderAIAnalysisModel,
    TenderItemModel,
    TenderMetadataModel,
    TenderModel,
    TenderStatusModel,
)
from app.infrastructure.repositories.user_model import UserModel

__all__ = [
    "BuyerInstitutionModel",
    "DeepAnalysisModel",
    "MatchingResultModel",
    "NotificationDeliveryModel",
    "NotificationModel",
    "NotificationPreferenceModel",
    "QuestionModel",
    "RegionModel",
    "SavedTenderModel",
    "SupplierModel",
    "TenderAIAnalysisModel",
    "TenderItemModel",
    "TenderMetadataModel",
    "TenderModel",
    "TenderStatusModel",
    "UserModel",
]
