import os
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
from magic_pdf.pipe.UNIPipe import UNIPipe

image_writer = DiskReaderWriter("./images")
image_dir = str(os.path.basename("./images"))

jso_useful_key = {"_pdf_type": "", "model_list": []}
pdf_bytes = open("./ICST24_Course_Mapping.pdf", "rb").read()
pipe: UNIPipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer)
pipe.pipe_classify()
pipe.pipe_analyze()
pipe.pipe_parse()
md_content: str = pipe.pipe_mk_markdown(image_dir, drop_mode="none")
