from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from datetime import datetime
import shutil
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "digitalrezeki_rental"


@app.route("/", methods=["GET", "POST"])
def login():

    if "login" in session:
        return redirect("/dashboard")

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            session["login"] = True

            return redirect("/dashboard")

        return "<h1>Username atau Password Salah</h1>"

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():

    if "login" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM komputer")
    komputer = cursor.fetchall()

    cursor.execute("""
    SELECT COUNT(*)
    FROM komputer
    WHERE status='Dipakai'
    """)
    pc_aktif = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COALESCE(SUM(total_bayar),0)
    FROM transaksi
    """)
    total_pendapatan = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM transaksi
    """)
    jumlah_transaksi = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM komputer")
    total_pc = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM komputer
    WHERE status='Kosong'
    """)
    pc_kosong = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        komputer=komputer,
        pc_aktif=pc_aktif,
        total_pendapatan=total_pendapatan,
        jumlah_transaksi=jumlah_transaksi,
        total_pc=total_pc,
        pc_kosong=pc_kosong
    )


@app.route("/start/<int:id_pc>")
def start_rental(id_pc):

    waktu_mulai = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE komputer
        SET status='Dipakai',
            jam_mulai=?
        WHERE id=?
        """,
        (waktu_mulai, id_pc)
    )

    conn.commit()
    conn.close()

    return f"""
    <h2>Rental Dimulai</h2>
    <p>Mulai: {waktu_mulai}</p>
    <a href="/">Kembali ke Login</a>
    """

@app.route("/stop/<int:id_pc>")
def stop_rental(id_pc):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT nama_pc, jam_mulai FROM komputer WHERE id=?",
        (id_pc,)
    )

    data = cursor.fetchone()

    nama_pc = data[0]
    jam_mulai = data[1]

    waktu_selesai = datetime.now()

    mulai = datetime.strptime(
        jam_mulai,
        "%Y-%m-%d %H:%M:%S"
    )

    durasi = (waktu_selesai - mulai).total_seconds() / 3600

    if durasi < 1:
        durasi = 1

    cursor.execute("""
    SELECT paket,harga
    FROM tarif
    ORDER BY id
    """)

    tarif_db = cursor.fetchall()

    total = 0

    if durasi <= 1:
        total = tarif_db[0][1]

    elif durasi <= 2:
        total = tarif_db[1][1]

    elif durasi <= 3:
        total = tarif_db[2][1]

    elif durasi <= 5:
        total = tarif_db[3][1]

    else:

        harga_5_jam = tarif_db[3][1]

        total = harga_5_jam + int((durasi - 5) * 3000)

    cursor.execute("""
        INSERT INTO transaksi
        (
            nama_pc,
            jam_mulai,
            jam_selesai,
            durasi_jam,
            total_bayar
        )
        VALUES (?, ?, ?, ?, ?)
    """,
    (
        nama_pc,
        jam_mulai,
        waktu_selesai.strftime("%Y-%m-%d %H:%M:%S"),
        round(durasi, 2),
        total
    ))

    cursor.execute("""
        UPDATE komputer
        SET status='Kosong',
            jam_mulai=NULL
        WHERE id=?
    """,
    (id_pc,))

    conn.commit()
    conn.close()

    return f"""
    <!DOCTYPE html>
    <html>

    <head>
    <title>Struk Rental</title>
    </head>

    <body>

    <h2>DIGITALREZEKI RENTAL</h2>

    <hr>

    <p><b>PC :</b> {nama_pc}</p>

    <p><b>Mulai :</b> {jam_mulai}</p>

    <p><b>Selesai :</b>
    {waktu_selesai.strftime("%Y-%m-%d %H:%M:%S")}
    </p>

    <p><b>Durasi :</b>
    {round(durasi,2)} Jam
    </p>

    <p><b>Total :</b>
    Rp {total:,}
    </p>

    <hr>

    <a href="/">
    Kembali Dashboard
    </a>

    </body>

    </html>
    """

@app.route("/laporan")
def laporan():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM transaksi
        ORDER BY id DESC
    """)
    transaksi = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(SUM(total_bayar),0)
        FROM transaksi
    """)
    total_pendapatan = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM transaksi
    """)
    total_transaksi = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "laporan.html",
        transaksi=transaksi,
        total_pendapatan=total_pendapatan,
        total_transaksi=total_transaksi
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

@app.route("/laporan_harian")
def laporan_harian():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    hari_ini = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT COUNT(*)
        FROM transaksi
        WHERE jam_selesai LIKE ?
    """, (hari_ini + "%",))

    jumlah_transaksi = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(total_bayar),0)
        FROM transaksi
        WHERE jam_selesai LIKE ?
    """, (hari_ini + "%",))

    total_pendapatan = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "laporan_harian.html",
        jumlah_transaksi=jumlah_transaksi,
        total_pendapatan=total_pendapatan,
        tanggal=hari_ini
    )

@app.route("/backup")
def backup_database():

    nama_file = datetime.now().strftime(
        "backup_%Y%m%d_%H%M%S.db"
    )

    tujuan = f"backup/{nama_file}"

    shutil.copy(
        "database.db",
        tujuan
    )

    return f"""
    <h2>Backup Berhasil</h2>

    <p>File:</p>

    <b>{nama_file}</b>

    <br><br>

    <a href="/">
        Kembali Dashboard
    </a>
    """

@app.route("/export_excel")
def export_excel():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM transaksi
        ORDER BY id DESC
    """)

    data = cursor.fetchall()

    conn.close()

    wb = Workbook()
    ws = wb.active

    ws.title = "Laporan Rental"

    ws.append([
        "ID",
        "PC",
        "Jam Mulai",
        "Jam Selesai",
        "Durasi",
        "Total Bayar"
    ])

    for row in data:
        ws.append(row)

    nama_file = "laporan_rental.xlsx"

    wb.save(nama_file)

    return send_file(
        nama_file,
        as_attachment=True
    )

@app.route("/tarif")
def tarif():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM tarif
    """)

    data_tarif = cursor.fetchall()

    conn.close()

    return render_template(
        "tarif.html",
        tarif=data_tarif
    )

@app.route("/edit_tarif/<int:id>", methods=["GET","POST"])
def edit_tarif(id):

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":

        harga = request.form["harga"]

        cursor.execute(
            """
            UPDATE tarif
            SET harga=?
            WHERE id=?
            """,
            (harga, id)
        )

        conn.commit()
        conn.close()

        return redirect("/tarif")

    cursor.execute(
        "SELECT * FROM tarif WHERE id=?",
        (id,)
    )

    data = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_tarif.html",
        tarif=data
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )