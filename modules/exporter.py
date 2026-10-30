from io import BytesIO
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

def export_workbook(df,start,end,source):
    out=BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        pd.DataFrame({"Keterangan":["Weekly Event Dashboard","Periode Mulai","Periode Akhir","Jumlah Event","File Sumber"],
                      "Nilai":["Training Event Schedule",start,end,len(df),source]}).to_excel(writer,sheet_name="Dashboard",index=False,startrow=2)
        df.to_excel(writer,sheet_name="Event Detail",index=False)
        wb=writer.book
        for ws in wb.worksheets:
            ws.sheet_view.showGridLines=False
            ws.freeze_panes="A2" if ws.title=="Event Detail" else "A4"
            if ws.title=="Dashboard":
                ws["A1"]="WEEKLY EVENT DASHBOARD"
                ws["A1"].font=Font(size=16,bold=True,color="173B63")
                for c in ws[3]:
                    c.fill=PatternFill("solid",fgColor="173B63"); c.font=Font(color="FFFFFF",bold=True)
            else:
                for c in ws[1]:
                    c.fill=PatternFill("solid",fgColor="173B63"); c.font=Font(color="FFFFFF",bold=True)
            for col in ws.columns:
                width=max(12,min(42,max((len(str(c.value)) if c.value is not None else 0) for c in col)+3))
                ws.column_dimensions[get_column_letter(col[0].column)].width=width
                for c in col: c.alignment=Alignment(vertical="center",wrap_text=True)
    out.seek(0)
    return out.getvalue()
