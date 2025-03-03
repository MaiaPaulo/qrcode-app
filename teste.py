# app.py
import streamlit as st
import qrcode
import os
import sqlite3
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime
import uuid
from PIL import Image
import sqlite3
from contextlib import contextmanager
import numpy as np
from PIL import Image
from io import BytesIO

# Configurações iniciais
st.set_page_config(page_title="Catálogo de Produtos", page_icon="📦")


# Configuração otimizada do banco de dados
@contextmanager
def get_db_connection():
    conn = sqlite3.connect('products.db', timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")  # Melhora concorrência
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS products
                     (id TEXT PRIMARY KEY,
                      name TEXT,
                      description TEXT,
                      creation_date TEXT,
                      image_path TEXT)''')

def insert_product(product_id, name, description, creation_date, image_path):
    with get_db_connection() as conn:
        conn.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)",
                    (product_id, name, description, creation_date, image_path))
        conn.commit()  # Commit explícito

def get_product(product_id):
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM products WHERE id=?", (product_id,))
        return cursor.fetchone()


# Diretórios
os.makedirs('product_images', exist_ok=True)
init_db()

# Interface principal
st.sidebar.title("Navegação")
page = st.sidebar.radio("Selecione a página:", ["Gerar QR Code", "Ler QR Code", "Ver Produtos Cadastrados"])

if page == "Gerar QR Code":
    st.title("📷 Gerador de QR Code para Produtos")

    # Inicializar variáveis de estado
    if 'generated' not in st.session_state:
        st.session_state.generated = False
        st.session_state.qr_bytes = None
        st.session_state.product_name = ""
        st.session_state.image_path = ""

    with st.form("product_form"):
        name = st.text_input("Nome do Produto*", max_chars=50)
        description = st.text_area("Descrição do Produto", height=100)
        image_file = st.file_uploader("Upload da Imagem do Produto*",
                                      type=['jpg', 'jpeg', 'png'])
        submitted = st.form_submit_button("Gerar QR Code")

        if submitted:
            if not name or not image_file:
                st.error("Preencha todos os campos obrigatórios (*)")
                st.session_state.generated = False
            else:
                # Processamento dos dados
                product_id = str(uuid.uuid4())
                creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                image_path = f"product_images/{product_id}.{image_file.name.split('.')[-1]}"

                with open(image_path, "wb") as f:
                    f.write(image_file.getbuffer())

                insert_product(product_id, name, description, creation_date, image_path)

                # Gerar QR Code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(product_id)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")

                # Converter para bytes
                img_buffer = BytesIO()
                qr_img.save(img_buffer, format="PNG")
                st.session_state.qr_bytes = img_buffer.getvalue()
                st.session_state.product_name = name
                st.session_state.generated = True

    # Exibir resultados e download FORA do formulário
    if st.session_state.generated:
        st.success("✅ QR Code gerado com sucesso!")
        col1, col2 = st.columns(2)
        with col1:
            qr_array = np.array(Image.open(BytesIO(st.session_state.qr_bytes)))
            st.image(qr_array,
                     caption="QR Code do Produto",
                     use_container_width=True,
                     channels="RGB")
        with col2:
            st.image(image_path, caption="Imagem do Produto", width=300)

        # Botão de download
        st.download_button(
            label="Baixar QR Code",
            data=st.session_state.qr_bytes,
            file_name=f"qr_code_{st.session_state.product_name}.png",
            mime="image/png"
        )

elif page == "Ler QR Code":
    st.title("🔍 Leitor de QR Code")

    # Opção de leitura
    scan_method = st.radio("Escolha o método de leitura:",
                           ["Usar Câmera", "Upload de Imagem"])

    detected_data = None

    if scan_method == "Usar Câmera":
        # Usar a câmera do dispositivo
        camera_image = st.camera_input("Aponte a câmera para o QR Code")

        if camera_image:
            try:
                # Converter para OpenCV
                image = np.array(Image.open(camera_image))
                decoded_objects = decode(image)

                if decoded_objects:
                    detected_data = decoded_objects[0].data.decode()
                else:
                    st.error("Nenhum QR Code detectado")
            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")

    else:
        # Upload de imagem
        uploaded_file = st.file_uploader("Carregue uma imagem com QR Code",
                                         type=['jpg', 'jpeg', 'png'])
        if uploaded_file:
            try:
                image = np.array(Image.open(uploaded_file))
                decoded_objects = decode(image)

                if decoded_objects:
                    detected_data = decoded_objects[0].data.decode()
                else:
                    st.error("Nenhum QR Code detectado na imagem")
            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")

    # Processar dados detectados
    if detected_data:
        product = get_product(detected_data)
        if product:
            st.success("✅ Produto encontrado!")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Informações do Produto")
                st.write(f"**Nome:** {product[1]}")
                st.write(f"**Descrição:** {product[2]}")
                st.write(f"**Data de Cadastro:** {product[3]}")
            with col2:
                st.image(product[4], caption="Imagem do Produto", width=300)
        else:
            st.error("❌ Produto não encontrado no banco de dados")

# Rodar o app
if __name__ == '__main__':
    st.write("Para acesso mobile:")
    st.write("1. Execute no terminal: `streamlit run app.py --server.address 0.0.0.0`")
    st.write("2. Use o ngrok para HTTPS: `ngrok http 8501`")
    st.write("3. Acesse o link HTTPS fornecido pelo ngrok")