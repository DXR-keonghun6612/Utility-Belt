from python_toolbox.project import Registry
from graphics.core.pass_.base import Base_Pass

# 렌더 패스 등록 레지스트리 (Base_Pass 서브클래스 전용)
Pass_Registry: Registry = Registry("RenderPassRegistry", Base_Pass)
