const fs=require('fs'); let s=fs.readFileSync('main.py','utf8');
const start=s.indexOf('@app.get("/api/analytics/meta")');
const end=s.indexOf('@app.delete("/api/analytics/clear")',start);
if(start<0||end<0)throw Error('Missing API markers');
const api=`def analytics_filtered_rows(db, start_date=None, end_date=None):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="Start Date must be on or before End Date")
    query = db.query(models.AnalyticsSalesRow)
    if start_date:
        query = query.filter(models.AnalyticsSalesRow.sale_date >= start_date)
    if end_date:
        query = query.filter(models.AnalyticsSalesRow.sale_date <= end_date)
    return query.order_by(models.AnalyticsSalesRow.sale_date, models.AnalyticsSalesRow.id).all()


@app.get("/api/analytics/meta")
def analytics_meta(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    upload = db.query(models.AnalyticsUpload).order_by(models.AnalyticsUpload.id.desc()).first()
    stores = sorted({r[0] or "Unknown" for r in db.query(models.AnalyticsSalesRow.store).distinct().all()})
    return {
        "has_data": bool(upload), "divisions": list(analytics_calc.CATEGORIES),
        "categories": list(analytics_calc.CATEGORIES), "stores": stores,
        "can_upload": auth.has_admin_access(current_user),
        "last_upload": {"file_name": upload.source_file, "uploaded_by": upload.uploaded_by_username,
                        "uploaded_at": upload.created_date, "row_count": upload.row_count,
                        "sheet_count": upload.sheet_count, "date_from": upload.date_from,
                        "date_to": upload.date_to} if upload else None,
    }


@app.get("/api/analytics/dashboard")
def analytics_dashboard(
    division: Optional[str] = Query(None), store: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None), end_date: Optional[date] = Query(None),
    current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db),
):
    source_rows = analytics_filtered_rows(db, start_date, end_date)
    rows, quality = analytics_calc.project(source_rows, detect_division_code, division, store, search)
    result = build_analytics_dashboard(rows)
    result["advanced"] = analytics_calc.advanced_stats(rows)
    result["quality"] = quality
    result["gst"] = {"rate": 18, "basis": "inclusive", "sales_gst": round(sum(r.sales_gst for r in rows), 2),
                     "cost_gst": round(sum(r.cost_gst for r in rows), 2),
                     "sales_before_gst": round(sum(r.sales_before_gst for r in rows), 2),
                     "cost_before_gst": round(sum(r.cost_before_gst for r in rows), 2)}
    result["filters"] = {"division": division or "ALL", "store": store or "ALL", "search": search or "",
                         "start_date": start_date, "end_date": end_date}
    return result


@app.get("/api/analytics/items")
def analytics_items(
    division: Optional[str] = Query(None), store: Optional[str] = Query(None), search: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None), end_date: Optional[date] = Query(None),
    view: str = Query("included", pattern="^(included|review|excluded|all)$"),
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
    current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db),
):
    rows, quality = analytics_calc.project(analytics_filtered_rows(db, start_date, end_date), detect_division_code,
                                         division, store, search, view)
    offset = (page - 1) * page_size
    return {"items": [vars(r) for r in rows[offset:offset+page_size]], "total": len(rows), "page": page,
            "page_size": page_size, "quality": quality, "amount_basis": "GST inclusive (18%)"}


@app.get("/api/analytics/export")
def analytics_export(
    division: Optional[str] = Query(None), store: Optional[str] = Query(None), search: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None), end_date: Optional[date] = Query(None),
    view: str = Query("included", pattern="^(included|review|excluded|all)$"),
    current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db),
):
    rows, _ = analytics_calc.project(analytics_filtered_rows(db, start_date, end_date), detect_division_code,
                                    division, store, search, view)
    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Voucher", "Item", "Category", "Store", "Brand", "Qty", "Sales before GST",
                     "Sales GST 18%", "Sales incl GST", "Cost before GST", "Cost GST 18%", "Cost incl GST",
                     "Profit incl GST", "Status", "Review reason"])
    for r in rows:
        writer.writerow([safe(v) for v in [r.sale_date.isoformat() if r.sale_date else "", r.vch_no, r.item,
            analytics_calc.CATEGORIES.get(r.division, r.division), r.store, r.brand, r.qty,
            r.sales_before_gst, r.sales_gst, r.sales_amt, r.cost_before_gst, r.cost_gst, r.cost_amt,
            r.profit_loss, r.status, r.exclusion_reason]])
    return Response(content=("\\ufeff"+buffer.getvalue()).encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="AI_Analysis_GST18.csv"'})


`;
s=s.slice(0,start)+api+s.slice(end);
// Apply the same normalization/classification to the legacy direct upload API.
let a=s.indexOf('def upload_analytics_file('), b=s.indexOf('def analytics_filtered_rows',a);
let block=s.slice(a,b).replace('file: UploadFile = File(...),','file: UploadFile = File(...),\n    amount_basis: str = Form("exclusive"),');
block=block.replace('    # Replace the previous dataset wholesale',`    try:
        parsed_rows = build_staged_rows(analytics_calc.normalize_upload(parsed_rows, amount_basis))
    except (ValueError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    allowed = {column.name for column in models.AnalyticsSalesRow.__table__.columns}
    parsed_rows = [{k: v for k, v in r.items() if k in allowed} for r in parsed_rows]

    # Replace the previous dataset wholesale`);
s=s.slice(0,a)+block+s.slice(b);
// A failed insert must not erase the previous upload: keep replacement atomic.
for(const name of ['commit_staged_file','upload_analytics_file']){
 a=s.indexOf('def '+name+'('); b=s.indexOf('\n\n@app.',a);
 if(b<0)b=s.indexOf('\ndef analytics_filtered_rows',a);
 block=s.slice(a,b);
 block=block.replace('    db.query(models.AnalyticsUpload).delete()\n    db.commit()', '    db.query(models.AnalyticsUpload).delete()\n    db.flush()');
 block=block.replace('    db.add(upload_record)\n    db.commit()\n    db.refresh(upload_record)', '    db.add(upload_record)\n    db.flush()');
 s=s.slice(0,a)+block+s.slice(b);
}
fs.writeFileSync('main.py',s);
