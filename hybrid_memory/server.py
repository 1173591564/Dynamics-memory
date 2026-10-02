"""HTTP 入口兼容垫片（P5）：实现已迁入 service.* / transport.*。"""
from .service.service import MemoryService, ProposalRejected
from .transport.bootstrap import build_default_service, main
from .transport.http import serve

if __name__ == "__main__":
    main()
