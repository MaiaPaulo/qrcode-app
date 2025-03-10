import streamlit as st
import qrcode
import os
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime
import uuid
from PIL import Image
import pandas as pd
import numpy as np
from io import BytesIO
from supabase import create_client, Client


# Configurações do Supabase

supabase_url = st.secrets.supabase.supabase_url
supabase_key = st.secrets.supabase.supabase_key
bucket_name = st.secrets.supabase.bucket_name

supabase: Client = create_client(supabase_url, supabase_key)

st.set_page_config(page_title="Catálogo de Produtos", page_icon="📦")


# Funções do Banco de Dados
def init_db():
    # A tabela será criada manualmente no painel do Supabase
    pass


def insert_product(product_id, name, description, creation_date, image_url):
    try:
        response = supabase.table('products').insert({
            "id": product_id,
            "name": name,
            "description": description,
            "creation_date": creation_date,
            "image_url": image_url
        }).execute()
        return response
    except Exception as e:
        st.error(f"Erro ao inserir produto: {str(e)}")
        return None


def get_product(product_id):
    try:
        response = supabase.table('products').select("*").eq("id", product_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Erro ao buscar produto: {str(e)}")
        return None


def get_all_products():
    try:
        response = supabase.table('products').select("*").order("creation_date", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao buscar produtos: {str(e)}")
        return []


# Função para upload de imagens
def upload_image(image_file, product_id):
    try:
        file_extension = image_file.name.split('.')[-1]
        file_path = f"{product_id}.{file_extension}"

        # Upload para o Supabase Storage (sintaxe oficial mais recente)
        res = supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=image_file.getvalue(),
            file_options={"content-type": image_file.type}  # Nome correto do parâmetro
        )

        # Obter URL pública
        return supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
    except Exception as e:
        st.error(f"Erro no upload da imagem: {str(e)}")
        return None


# Interface principal
st.sidebar.title("Navegação")
page = st.sidebar.radio("Selecione a página:", ["Gerar QR Code", "Ler QR Code", "Ver Produtos Cadastrados"])

if page == "Gerar QR Code":
    st.title("📷 Gerador de QR Code para Produtos")

    # Inicialização do Session State
    if 'generated' not in st.session_state:
        st.session_state.generated = False
        st.session_state.qr_bytes = None
        st.session_state.product_name = ""
        st.session_state.image_url = ""

    with st.form("product_form"):
        name = st.text_input("Nome do Produto*", max_chars=50)
        description = st.text_area("Descrição do Produto", height=100)
        image_file = st.file_uploader("Upload da Imagem do Produto*", type=['jpg', 'jpeg', 'png'])
        submitted = st.form_submit_button("Gerar QR Code")

        if submitted:
            if not name or not image_file:
                st.error("Preencha todos os campos obrigatórios (*)")
                st.session_state.generated = False
            else:
                # Lógica de cadastro e geração do QR Code
                product_id = str(uuid.uuid4())
                image_url = upload_image(image_file, product_id)

                if image_url:
                    insert_product(product_id, name, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   image_url)

                    # Geração do QR Code
                    qr = qrcode.make(product_id)
                    img_buffer = BytesIO()
                    qr.save(img_buffer, format="PNG")
                    st.session_state.qr_bytes = img_buffer.getvalue()
                    st.session_state.product_name = name
                    st.session_state.generated = True
                    st.success("✅ Produto cadastrado com sucesso!")

    # Botão de download FORA do formulário
    if st.session_state.generated:
        st.download_button(
            label="Baixar QR Code",
            data=st.session_state.qr_bytes,
            file_name=f"qr_code_{st.session_state.product_name}.png",
            mime="image/png"
        )

# Seção de leitura mantém a mesma lógica, modificando apenas o acesso à imagem
elif page == "Ler QR Code":
    st.title("🔍 Leitor de QR Code")

    # Inicialização da variável
    detected_data = None
    scan_method = st.radio("Escolha o método de leitura:", ["Usar Câmera", "Upload de Imagem"])


    # Função de decodificação
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


    # Lógica de leitura por câmera
    if scan_method == "Usar Câmera":
        camera_image = st.camera_input("Aponte a câmera para o QR Code")
        if camera_image:
            try:
                image = np.array(Image.open(camera_image).convert('L'))
                detected_data = decode_qr(image)
            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")
                detected_data = None

    # Lógica de leitura por upload
    else:
        uploaded_file = st.file_uploader("Carregue uma imagem com QR Code", type=['jpg', 'jpeg', 'png'])
        if uploaded_file:
            try:
                image = np.array(Image.open(uploaded_file).convert('L'))
                detected_data = decode_qr(image)
            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")
                detected_data = None

    # Exibição dos resultados
    if detected_data:
        try:
            product_id = detected_data.strip()
            product = get_product(product_id)

            if product:
                st.success("✅ QR Code detectado com sucesso!")
                st.subheader("📋 Detalhes do Produto")

                # Layout em colunas
                col1, col2 = st.columns([1, 2])

                with col1:
                    # Exibir imagem do produto
                    st.image(
                        product['image_url'],
                        caption="Foto do Produto",
                        use_container_width=True
                    )

                    # Gerar QR Code para exibição
                    qr_img = qrcode.make(product_id)
                    st.image(
                        np.array(qr_img.convert("RGB")),
                        caption="QR Code do Produto",
                        use_container_width=True
                    )

                with col2:
                    # Exibir detalhes textuais
                    st.markdown(f"""
                        **Nome do Produto:**  
                        {product['name']}

                        **Descrição:**  
                        {product['description'] or 'Sem descrição'}

                        **Data de Cadastro:**  
                        {datetime.strptime(product['creation_date'], '%Y-%m-%dT%H:%M:%S').strftime('%d/%m/%Y %H:%M')}

                        **ID Único:**  
                        `{product_id}`
                        """)
                    # Botão para copiar ID
                    if st.button("📋 Copiar ID"):
                        st.session_state.clipboard = product_id
                        st.toast("ID copiado para a área de transferência!")

            else:
                st.error("⚠️ Produto não encontrado no banco de dados")
                st.markdown(f"Dados recebidos: `{detected_data}`")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            st.write("Detalhes técnicos:", detected_data)

# Seção de visualização de produtos
elif page == "Ver Produtos Cadastrados":
    st.title("📦 Produtos Cadastrados")

    products = get_all_products()

    if not products:
        st.info("Nenhum produto cadastrado ainda.")
    else:
        st.subheader(f"Total de produtos: {len(products)}")

        # Exibir em formato de tabela
        with st.expander("Ver tabela completa"):
            df = pd.DataFrame(products, columns=["ID", "Nome", "Descrição", "Data Criação", "Imagem URL"])
            st.dataframe(df[["Nome", "Descrição", "Data Criação"]], use_container_width=True)

        # Exibir detalhes de cada produto
        for product in products:
            with st.container():
                col1, col2, col3 = st.columns([1, 3, 1])

                with col1:
                    if product['image_url']:
                        st.image(product['image_url'], use_container_width=True)
                    else:
                        st.error("Imagem não encontrada")

                with col2:
                    st.subheader(product['name'])
                    st.write(product['description'] or "Sem descrição")
                    st.caption(
                        f"Cadastrado em: {datetime.strptime(product['creation_date'], '%Y-%m-%dT%H:%M:%S').strftime('%d/%m/%Y %H:%M')}")

                with col3:
                    # Botão de exclusão
                    delete_key = f"del_{product['id']}"
                    if st.button("🗑️ Excluir", key=delete_key, type="secondary"):
                        st.session_state['product_to_delete'] = product['id']

                    # Confirmação de exclusão
                    if 'product_to_delete' in st.session_state and st.session_state['product_to_delete'] == product[
                        'id']:
                        st.warning("Tem certeza que deseja excluir este produto permanentemente?")
                        col_confirm, col_cancel = st.columns(2)

                        with col_confirm:
                            if st.button("✅ Confirmar Exclusão", key=f"confirm_{product['id']}"):
                                try:
                                    # Excluir do banco de dados
                                    supabase.table('products').delete().eq('id', product['id']).execute()

                                    # Excluir imagem do Storage
                                    if product['image_url']:
                                        file_path = product['image_url'].split('/')[-1]
                                        supabase.storage.from_(BUCKET_NAME).remove([file_path])

                                    st.success("Produto excluído com sucesso!")
                                    del st.session_state['product_to_delete']
                                    st.rerun()

                                except Exception as e:
                                    st.error(f"Erro ao excluir produto: {str(e)}")

                        with col_cancel:
                            if st.button("❌ Cancelar", key=f"cancel_{product['id']}"):
                                del st.session_state['product_to_delete']
                                st.rerun()

                st.divider()