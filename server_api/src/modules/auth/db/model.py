"""인증/얼굴 인식 관련 보조 ORM 모델.

user_table과 연결되는 얼굴 임베딩 저장 구조를 분리해서 관리한다.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.lib.database import Base


# Face ID 등록 여부를 빠르게 확인하기 위한 텍스트 벡터 저장소
class VectorTable(Base):
	__tablename__ = "vector_table"

	# user_table.employee_no와 1:1로 매핑되는 키
	employee_no: Mapped[str] = mapped_column(
		String(64),
		ForeignKey("user_table.employee_no"),
		primary_key=True,
		index=True,
	)
	# 등록 여부 확인과 간단한 조회 최적화를 위한 벡터 표현
	face_embedding: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)


# 실제 얼굴 매칭에 사용하는 원본 임베딩 JSON 저장소
class FaceEmbeddingTable(Base):
	__tablename__ = "face_embedding_table"

	# user_table.employee_no와 1:1로 매핑되는 키
	employee_no: Mapped[str] = mapped_column(
		String(64),
		ForeignKey("user_table.employee_no"),
		primary_key=True,
		index=True,
	)
	# 얼굴 인식 엔진 비교에 직접 쓰는 float 벡터 배열(JSON 직렬화)
	embedding_json: Mapped[str] = mapped_column(String, nullable=False)
