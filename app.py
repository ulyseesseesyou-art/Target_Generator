from flask import Flask, render_template_string, request, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import red, black, white
import tempfile
from io import BytesIO
from PIL import Image
from pdf2image import convert_from_bytes

app = Flask(__name__)

# --- HTML template ---
HTML_PAGE = """
<!doctype html>
<html>
<head>
<title>Target Generator</title>
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
label { display:inline-block; width: 150px; }
input[type=number], input[type=text] { width: 60px; }
input[type=submit] { margin-top: 10px; }
.preview { border:1px solid #ccc; margin-top: 20px; width:300px; height:300px; }
</style>
</head>
<body>
<h2>Target Generator</h2>
<form method="post">
<label>Columns:</label><input type="number" name="cols" value="{{cols}}" min="1"><br>
<label>Rows:</label><input type="number" name="rows" value="{{rows}}" min="1"><br>
<label>Outer Diameter (cm):</label><input type="number" step="0.1" name="outer" value="{{outer}}"><br>
<label>Number of Rings:</label><input type="number" name="rings" value="{{rings}}" min="1"><br>
<label>Rings to Fill (comma sep):</label><input type="text" name="fill_rings" value="{{fill_rings}}"><br>
<label>Fill Color:</label>
<select name="fill_color">
  <option value="Red" {% if fill_color=='Red' %}selected{% endif %}>Red</option>
  <option value="Black" {% if fill_color=='Black' %}selected{% endif %}>Black</option>
  <option value="Yellow" {% if fill_color=='Yellow' %}selected{% endif %}>Yellow</option>
  <option value="Blue" {% if fill_color=='Blue' %}selected{% endif %}>Blue</option>
</select><br>
<label>Bullseye:</label><input type="checkbox" name="bull" {% if bull %}checked{% endif %}>
<label>Bull Diameter (mm):</label><input type="number" name="bull_dia" step="0.1" value="{{bull_dia}}"><br>
<label>Crosshair:</label><input type="checkbox" name="cross" {% if cross %}checked{% endif %}><br>
<input type="submit" value="Generate PDF">
</form>

{% if preview %}
<h3>Single Target Preview</h3>
<img src="data:image/png;base64,{{preview}}" class="preview">
<br>
<a href="/download_pdf?{{query_string}}" target="_blank">Download PDF</a>
{% endif %}
</body>
</html>
"""

# --- Map colors ---
PDF_COLORS = {"Red": red, "Black": black, "Yellow": "yellow", "Blue": "blue"}

# --- Helper to generate PDF in memory ---
def create_pdf(params):
    cols = int(params.get("cols", 4))
    rows = int(params.get("rows", 5))
    outer_diameter = float(params.get("outer", 4)) * cm
    num_rings = int(params.get("rings", 5))
    fill_rings = [int(x.strip()) for x in params.get("fill_rings", "1,3").split(",") if x.strip()]
    draw_crosshairs = "cross" in params
    bullseye_on = "bull" in params
    bull_diameter = float(params.get("bull_dia", 2)) * mm
    bull_radius = bull_diameter / 2.0
    fill_color_pdf = PDF_COLORS.get(params.get("fill_color", "Red"), red)
    
    # Create PDF in memory
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    
    # Calculate margins to center grid
    margin_x = (A4[0] - cols*outer_diameter)/(cols+1)
    margin_y = (A4[1] - rows*outer_diameter - 15*mm)/(rows+1)  # reserve footer height
    top_margin = margin_y
    
    for row in range(rows):
        for col in range(cols):
            x = margin_x + (col + 0.5)*outer_diameter + col*margin_x
            y = A4[1] - (top_margin + (row + 0.5)*outer_diameter + row*margin_y)
            # Draw rings
            for i in range(num_rings, 0, -1):
                radius_outer = (outer_diameter/2)*(i/num_rings)
                radius_inner = (outer_diameter/2)*((i-1)/num_rings) if i>1 else 0
                c.setLineWidth(1)
                if i in fill_rings:
                    c.setFillColor(fill_color_pdf)
                    c.setStrokeColor(black)
                    c.circle(x, y, radius_outer, stroke=1, fill=1)
                    if radius_inner>0:
                        c.setFillColor(white)
                        c.circle(x, y, radius_inner, stroke=0, fill=1)
                else:
                    c.setStrokeColor(black)
                    c.setFillColor(white)
                    c.circle(x, y, radius_outer, stroke=1, fill=0)
            # Crosshairs
            if draw_crosshairs:
                cross_len = (outer_diameter/2) + 2*mm
                c.setLineWidth(1)
                c.line(x - cross_len, y, x + cross_len, y)
                c.line(x, y - cross_len, x, y + cross_len)
            # Bullseye
            if bullseye_on:
                c.setFillColor(black)
                c.circle(x, y, bull_radius, stroke=0, fill=1)
    
    # Footer
    footer_text = "Date: ___/___/____    Range: ___________    Pellet used: ____________    Weight: _________"
    c.setFont("Helvetica", 10)
    text_width = c.stringWidth(footer_text, "Helvetica", 10)
    footer_y = 10*mm
    c.drawString((A4[0]-text_width)/2, footer_y, footer_text)
    
    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

# --- Generate PNG preview ---
def create_preview(pdf_buffer):
    pages = convert_from_bytes(pdf_buffer.read(), dpi=150)
    img = pages[0]
    img.thumbnail((300,300))
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    import base64
    return base64.b64encode(buffered.getvalue()).decode()

@app.route("/", methods=["GET","POST"])
def index():
    params = request.form.to_dict()
    preview_img = None
    if request.method=="POST":
        pdf_buffer = create_pdf(params)
        preview_img = create_preview(pdf_buffer)
    return render_template_string(HTML_PAGE,
                                  preview=preview_img,
                                  query_string=request.query_string.decode(),
                                  cols=params.get("cols", 4),
                                  rows=params.get("rows", 5),
                                  outer=params.get("outer", 4),
                                  rings=params.get("rings",5),
                                  fill_rings=params.get("fill_rings","1,3"),
                                  fill_color=params.get("fill_color","Red"),
                                  bull="bull" in params,
                                  bull_dia=params.get("bull_dia",2),
                                  cross="cross" in params)

@app.route("/download_pdf")
def download_pdf():
    # Get params from query string
    params = request.args.to_dict()
    pdf_buffer = create_pdf(params)
    return send_file(pdf_buffer, as_attachment=True, download_name="Target.pdf", mimetype="application/pdf")

if __name__=="__main__":
    app.run(debug=True)
