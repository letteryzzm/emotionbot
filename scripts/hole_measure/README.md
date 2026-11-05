从参考装配模型 OBJ 里量每颗螺丝落在哪个零件、那个零件的孔径和孔深（判断热熔螺母规格）。
.venv/bin/python scripts/hole_measure/screws.py "upstream/Head_α2.0.33/Printing and Assembly/Reference Assembly (Open with Microsoft 3D Viewer or Blender).obj" <outdir>
.venv/bin/python scripts/hole_measure/depth.py <outdir>
结果整理在笔记 head/螺丝与热熔螺母清单.md
