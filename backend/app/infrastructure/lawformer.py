# Lawformer 编码器封装，支持基础模型和微调权重
from pathlib import Path
from threading import Lock
from typing import Optional

import numpy as np
import torch
from loguru import logger
from transformers import AutoModel, AutoTokenizer

from app.core.config import settings

_embedder: Optional["LawformerEmbedder"] = None
_embedder_lock = Lock()


class LawformerEmbedder:
    """Lawformer 文本向量化封装，支持微调权重加载"""

    def __init__(self, model_path: str, finetuned_path: str = ""):
        from app.core.config import settings
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        model_path_obj = Path(model_path)
        if not model_path_obj.is_absolute():
            model_path_obj = (Path(__file__).resolve().parents[2] / model_path_obj).resolve()
        resolved_model_path = str(model_path_obj)

        # HF_HOME 是 huggingface_hub 的根目录，实际 hub 缓存在其 hub/ 子目录
        # cache_dir 参数对应 HUGGINGFACE_HUB_CACHE，需要指向 {HF_HOME}/hub
        hf_home = settings.HF_HOME or ""
        cache_dir = None
        if hf_home:
            hf_home_obj = Path(hf_home)
            if not hf_home_obj.is_absolute():
                hf_home_obj = (Path(__file__).resolve().parents[2] / hf_home_obj).resolve()
            cache_dir = str((hf_home_obj / "hub").resolve())

        logger.info(f"加载 Lawformer 模型: {resolved_model_path} (device: {self.device}, cache_dir: {cache_dir})")

        local_only = settings.MODEL_OFFLINE_MODE
        self.tokenizer = AutoTokenizer.from_pretrained(resolved_model_path, trust_remote_code=True, cache_dir=cache_dir, local_files_only=local_only)
        self.model = AutoModel.from_pretrained(resolved_model_path, trust_remote_code=True, cache_dir=cache_dir, local_files_only=local_only)

        # 加载微调权重
        if finetuned_path:
            finetuned_path_obj = Path(finetuned_path)
            if not finetuned_path_obj.is_absolute():
                finetuned_path_obj = (Path(__file__).resolve().parents[2] / finetuned_path_obj).resolve()
            self._load_finetuned(str(finetuned_path_obj))
        else:
            logger.info("使用基础 Lawformer 模型")

        self.model.to(self.device)
        self.model.eval()
        logger.info("Lawformer 模型加载完成")

    def _load_finetuned(self, finetuned_path: str) -> None:
        """加载微调权重（backbone only）"""
        try:
            checkpoint = torch.load(finetuned_path, map_location="cpu", weights_only=True)

            # 提取 state_dict
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
                logger.info(f"微调权重 epoch={checkpoint.get('epoch')}, loss={checkpoint.get('loss')}")
            else:
                state_dict = checkpoint

            if not isinstance(state_dict, dict) or not state_dict:
                raise ValueError("微调权重不是有效的 state_dict")

            # 去除 backbone. 前缀（如果有）
            if any(k.startswith("backbone.") for k in state_dict):
                state_dict = {
                    k.removeprefix("backbone."): v
                    for k, v in state_dict.items()
                    if k.startswith("backbone.")
                    }
                logger.info("已提取 backbone 权重")

            result = self.model.load_state_dict(state_dict, strict=True)
            logger.info(f"微调权重加载完成，missing={len(result.missing_keys)}, unexpected={len(result.unexpected_keys)}")
        except Exception as e:
            # 查询模型和库向量必须处于同一向量空间，不能静默换成基础模型。
            raise RuntimeError("微调权重加载失败，请检查 FINETUNED_MODEL_PATH 和权重格式") from e

    def encode(self, text: str, max_length: int = 512, show_progress_bar: bool = False) -> np.ndarray:
        """编码单条文本，返回 (768,) 向量"""
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            max_length=max_length,
            truncation=True,
            padding=True,
            )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        vec = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        return vec[0]


def get_embedder() -> LawformerEmbedder:
    """获取全局 Lawformer 实例（懒加载）"""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                model_path = settings.LOCAL_MODEL_PATH
                finetuned_path = settings.FINETUNED_MODEL_PATH or ""
                logger.info(f"model_path={model_path!r}, finetuned_path={finetuned_path!r}")
                _embedder = LawformerEmbedder(model_path, finetuned_path)
    return _embedder
