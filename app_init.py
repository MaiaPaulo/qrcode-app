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
import pandas as pd
from contextlib import contextmanager
import numpy as np
from PIL import Image
from io import BytesIO


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
# Adicione esta nova função no banco de dados
def get_all_products():
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM products ORDER BY creation_date DESC")
        return cursor.fetchall()

# Diretórios
os.makedirs('product_images', exist_ok=True)
init_db()

# Interface principal
st.sidebar.title("Navegação")
page = st.sidebar.radio("Selecione a página:", ["Gerar QR Code", "Ler QR Code", "Ver Produtos Cadastrados"])

if page == "Gerar QR Code":
    st.title("📷 Gerador de QR Code para Produtos")

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
                product_id = str(uuid.uuid4())
                creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.image_path = f"product_images/{product_id}.{image_file.name.split('.')[-1]}"

                with open(st.session_state.image_path, "wb") as f:
                    f.write(image_file.getbuffer())

                insert_product(product_id, name, description, creation_date, st.session_state.image_path)

                # Geração do QR Code melhorada
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=20,
                    border=6,
                )
                qr.add_data(product_id)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")

                img_buffer = BytesIO()
                qr_img.save(img_buffer, format="PNG")
                st.session_state.qr_bytes = img_buffer.getvalue()
                st.session_state.product_name = name
                st.session_state.generated = True

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
            if os.path.exists(st.session_state.image_path):
                st.image(st.session_state.image_path, caption="Imagem do Produto", width=300)
            else:
                st.error("Imagem não encontrada")

        st.download_button(
            label="Baixar QR Code",
            data=st.session_state.qr_bytes,
            file_name=f"qr_code_{st.session_state.product_name}.png",
            mime="image/png"
        )

# Atualize a seção de leitura do QR Code
elif page == "Ler QR Code":
    st.title("🔍 Leitor de QR Code")

    scan_method = st.radio("Escolha o método de leitura:", ["Usar Câmera", "Upload de Imagem"])
    detected_data = None


    def decode_qr(image):
        try:
            # Converter para array numpy uint8
            if image.dtype == bool:
                image = image.astype(np.uint8) * 255

            # Converter para escala de cinza se necessário
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

            # Primeiro tentar com pyzbar
            decoded_objects = decode(image)
            if decoded_objects:
                return decoded_objects[0].data.decode('utf-8')

            # Se falhar, tentar com OpenCV
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(image)
            return data if data else None

        except Exception as e:
            st.error(f"Erro no processamento: {str(e)}")
            return None


    if scan_method == "Usar Câmera":
        camera_image = st.camera_input("Aponte a câmera para o QR Code")
        if camera_image:
            try:
                # Carregar imagem diretamente em escala de cinza
                image = np.array(Image.open(camera_image).convert('L'))
                detected_data = decode_qr(image)

            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")

    else:
        uploaded_file = st.file_uploader("Carregue uma imagem com QR Code", type=['jpg', 'jpeg', 'png'])
        if uploaded_file:
            try:
                # Carregar imagem em escala de cinza
                image = np.array(Image.open(uploaded_file).convert('L'))
                detected_data = decode_qr(image)

            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")

    if detected_data:
        st.success("✅ QR Code detectado com sucesso!")

        try:
            product_id = detected_data.strip()
            product = get_product(product_id)

            if product:
                st.subheader("📋 Detalhes do Produto")

                # Layout em colunas
                col1, col2 = st.columns([1, 2])

                with col1:
                    # Exibir imagem do produto
                    if os.path.exists(product[4]):
                        st.image(product[4],
                                 caption="Foto do Produto",
                                 use_container_width=True)
                    else:
                        st.error("Imagem não encontrada")

                    # Exibir QR Code novamente
                    qr_img = qrcode.make(product_id)
                    st.image(np.array(qr_img.convert("RGB")),
                             caption="QR Code do Produto",
                             use_container_width=True)

                with col2:
                    # Exibir detalhes textuais
                    st.markdown(f"""
                        **Nome do Produto:**  
                        {product[1]}

                        **Descrição:**  
                        {product[2] or 'Sem descrição'}

                        **Data de Cadastro:**  
                        {datetime.strptime(product[3], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}

                        **ID Único:**  
                        `{product[0]}`
                        """)

                    # Botão para copiar ID
                    if st.button("📋 Copiar ID"):
                        st.session_state.clipboard = product[0]
                        st.toast("ID copiado para a área de transferência!")

            else:
                st.error("⚠️ Produto não encontrado no banco de dados")
                st.markdown(f"Dados recebidos: `{detected_data}`")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            st.write("Detalhes técnicos:", detected_data)

elif page == "Ver Produtos Cadastrados":
    st.title("📦 Produtos Cadastrados")

# Buscar todos os produtos
    products = get_all_products()

    if not products:
        st.info("Nenhum produto cadastrado ainda.")
    else:
        st.subheader(f"Total de produtos: {len(products)}")

    # Exibir em formato de tabela
    with st.expander("Ver tabela completa"):
        df = pd.DataFrame(products, columns=["ID", "Nome", "Descrição", "Data Criação", "Caminho Imagem"])
        st.dataframe(df[["Nome", "Descrição", "Data Criação"]], use_container_width=True)

    # Exibir detalhes de cada produto
    for product in products:
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])
            with col1:
                if os.path.exists(product[4]):
                    st.image(product[4], use_container_width=True)
                else:
                    st.error("Imagem não encontrada")

            with col2:
                st.subheader(product[1])
                st.write(product[2])
                st.caption(f"Cadastrado em: {product[3]}")

            with col3:
                # Botão para ver QR Code
                if st.button("Ver QR Code", key=f"qr_{product[0]}"):
                    qr = qrcode.make(product[0])
                    st.image(np.array(qr.convert("RGB")),
                             caption=f"QR Code - {product[1]}",
                             use_container_width=True)

                # Botão para excluir (opcional)
                # Dentro da página "Ver Produtos Cadastrados"
                if st.button("Excluir", key=f"del_{product[0]}", type="primary"):
                    # Confirmar exclusão
                    if st.warning("Tem certeza que deseja excluir este produto?"):
                        # Deletar imagem
                        if os.path.exists(product[4]):
                            os.remove(product[4])
                        # Deletar do banco de dados
                        with get_db_connection() as conn:
                            conn.execute("DELETE FROM products WHERE id=?", (product[0],))
                            conn.commit()
                        st.success("Produto excluído com sucesso!")
                        st.rerun()  # <-- Linha corrigida

            st.divider()

# Rodar o app
if __name__ == '__main__':
    st.write("Para acesso mobile:")
    st.write("1. Execute no terminal: `streamlit run app_init.py --server.address 0.0.0.0`")
    st.write("2. Use o ngrok para HTTPS: `ngrok http 8501`")
    st.write("3. Acesse o link HTTPS fornecido pelo ngrok")