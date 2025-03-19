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

# Configuração de categorias
CATEGORIAS = {
    "nexthub": 100001,
    "nextonline": 150001,
    "nextevents": 200001,
    "federação": 250001,
    "nexttech": 300001,
    "nextmedia": 350001,
    "nexteducation": 400001
}

st.set_page_config(page_title="Catálogo de Produtos", page_icon="📦")


# Funções do Banco de Dados
def init_db():
    pass


def insert_product(product_id, category, name, description, creation_date, image_url, qr_code_url):
    try:
        response = supabase.table('products').insert({
            "id": product_id,
            "category": category,
            "name": name,
            "description": description,
            "creation_date": creation_date,
            "image_url": image_url,
            "qr_code_url": qr_code_url
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


# Funções de Upload
def upload_image(image_file, product_id):
    try:
        file_extension = image_file.name.split('.')[-1]
        file_path = f"{product_id}.{file_extension}"

        res = supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=image_file.getvalue(),
            file_options={"content-type": image_file.type}
        )
        return supabase.storage.from_(bucket_name).get_public_url(file_path)
    except Exception as e:
        st.error(f"Erro no upload da imagem: {str(e)}")
        return None


def upload_qr_code(qr_bytes, product_id):
    try:
        file_path = f"{product_id}_qrcode.png"
        res = supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=qr_bytes,
            file_options={"content-type": "image/png"}
        )
        return supabase.storage.from_(bucket_name).get_public_url(file_path)
    except Exception as e:
        st.error(f"Erro no upload do QR code: {str(e)}")
        return None


# Interface Principal
st.sidebar.title("Navegação")
page = st.sidebar.radio("Selecione a página:", ["Gerar QR Code", "Ler QR Code", "Ver Produtos Cadastrados"])

if page == "Gerar QR Code":
    st.title("📷 Gerador de QR Code para Produtos")

    if 'generated' not in st.session_state:
        st.session_state.generated = False
        st.session_state.qr_bytes = None
        st.session_state.product_name = ""
        st.session_state.image_url = ""

    with st.form("product_form"):
        category = st.selectbox(
            "Categoria do Produto*",
            options=list(CATEGORIAS.keys()),
            index=0
        )
        name = st.text_input("Nome do Produto*", max_chars=50)
        description = st.text_area("Descrição do Produto", height=100)
        image_file = st.file_uploader("Upload da Imagem do Produto*", type=['jpg', 'jpeg', 'png'])
        submitted = st.form_submit_button("Gerar QR Code")

        if submitted:
            if not name or not image_file or not category:
                st.error("Preencha todos os campos obrigatórios (*)")
                st.session_state.generated = False
            else:
                try:
                    # Obter último ID da categoria
                    response = supabase.table('products') \
                        .select('id') \
                        .eq('category', category) \
                        .order('id', desc=True) \
                        .limit(1) \
                        .execute()

                    last_id = response.data[0]['id'] if response.data else None
                    next_id = last_id + 1 if last_id else CATEGORIAS[category]

                    product_id = next_id
                    image_url = upload_image(image_file, product_id)

                    if image_url:
                        qr = qrcode.make(str(product_id))
                        img_buffer = BytesIO()
                        qr.save(img_buffer, format="PNG")
                        qr_bytes = img_buffer.getvalue()
                        qr_code_url = upload_qr_code(qr_bytes, product_id)

                        if qr_code_url:
                            insert_product(
                                product_id=product_id,
                                category=category,
                                name=name,
                                description=description,
                                creation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                image_url=image_url,
                                qr_code_url=qr_code_url
                            )

                            st.session_state.qr_bytes = qr_bytes
                            st.session_state.product_name = name
                            st.session_state.generated = True
                            st.success("✅ Produto cadastrado com sucesso!")

                except Exception as e:
                    st.error(f"Erro ao gerar ID do produto: {str(e)}")

    if st.session_state.generated:
        st.download_button(
            label="Baixar QR Code",
            data=st.session_state.qr_bytes,
            file_name=f"qr_code_{st.session_state.product_name}.png",
            mime="image/png"
        )

elif page == "Ler QR Code":
    st.title("🔍 Leitor de QR Code")

    detected_data = None
    scan_method = st.radio("Escolha o método de leitura:", ["Usar Câmera", "Upload de Imagem"])


    def decode_qr(image):
        try:
            if image.dtype == bool:
                image = image.astype(np.uint8) * 255

            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

            decoded_objects = decode(image)
            if decoded_objects:
                return decoded_objects[0].data.decode('utf-8')

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
                image = np.array(Image.open(camera_image).convert('L'))
                detected_data = decode_qr(image)
            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")
                detected_data = None
    else:
        uploaded_file = st.file_uploader("Carregue uma imagem com QR Code", type=['jpg', 'jpeg', 'png'])
        if uploaded_file:
            try:
                image = np.array(Image.open(uploaded_file).convert('L'))
                detected_data = decode_qr(image)
            except Exception as e:
                st.error(f"Erro na leitura: {str(e)}")
                detected_data = None

    if detected_data:
        try:
            product_id = int(detected_data.strip())
            product = get_product(product_id)

            if product:
                st.success("✅ QR Code detectado com sucesso!")
                st.subheader("📋 Detalhes do Produto")

                col1, col2 = st.columns([1, 2])

                with col1:
                    st.image(
                        product['image_url'],
                        caption="Foto do Produto",
                        use_container_width=True
                    )
                    qr_img = qrcode.make(str(product_id))
                    st.image(
                        np.array(qr_img.convert("RGB")),
                        caption="QR Code do Produto",
                        use_container_width=True
                    )

                with col2:
                    st.markdown(f"""
                        **Categoria:**  
                        {product['category'].upper()}

                        **Nome do Produto:**  
                        {product['name']}

                        **Descrição:**  
                        {product['description'] or 'Sem descrição'}

                        **Data de Cadastro:**  
                        {datetime.strptime(product['creation_date'], '%Y-%m-%dT%H:%M:%S').strftime('%d/%m/%Y %H:%M')}

                        **ID Único:**  
                        `{product_id}`
                        """)
                    if st.button("📋 Copiar ID"):
                        st.session_state.clipboard = product_id
                        st.toast("ID copiado para a área de transferência!")

            else:
                st.error("⚠️ Produto não encontrado no banco de dados")
                st.markdown(f"Dados recebidos: `{detected_data}`")

        except Exception as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            st.write("Detalhes técnicos:", detected_data)

elif page == "Ver Produtos Cadastrados":
    st.title("📦 Produtos Cadastrados")

    selected_category = st.selectbox(
        "Filtrar por categoria:",
        options=["Todas"] + list(CATEGORIAS.keys())
    )

    products = get_all_products()

    if selected_category != "Todas":
        products = [p for p in products if p['category'] == selected_category]

    if not products:
        st.info("Nenhum produto cadastrado ainda.")
    else:
        st.subheader(f"Total de produtos: {len(products)}")

        with st.expander("Ver tabela completa"):
            df = pd.DataFrame(products,
                              columns=["id", "category", "name", "description", "creation_date", "image_url",
                                       "qr_code_url"])
            st.dataframe(df[["category", "name", "description", "creation_date"]], use_container_width=True)

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
                    st.caption(f"Categoria: {product['category'].upper()}")
                    st.write(product['description'] or "Sem descrição")
                    st.caption(
                        f"Cadastrado em: {datetime.fromisoformat(product['creation_date'].replace('Z', '+00:00')).strftime('%d/%m/%Y %H:%M')}")

                with col3:
                    if product.get('qr_code_url'):
                        try:
                            qr_file_path = f"{product['id']}_qrcode.png"
                            qr_data = supabase.storage.from_(bucket_name).download(qr_file_path)

                            st.download_button(
                                label="⬇️ QR Code",
                                data=qr_data,
                                file_name=f"qr_{product['name']}.png",
                                mime="image/png",
                                key=f"qr_{product['id']}"
                            )
                        except Exception as e:
                            st.error(f"Erro ao baixar QR Code: {str(e)}")

                    delete_key = f"del_{product['id']}"
                    if st.button("🗑️ Excluir", key=delete_key, type="secondary"):
                        st.session_state['product_to_delete'] = product['id']

                    if 'product_to_delete' in st.session_state and st.session_state['product_to_delete'] == product[
                        'id']:
                        st.warning("Tem certeza que deseja excluir este produto permanentemente?")
                        col_confirm, col_cancel = st.columns(2)

                        with col_confirm:
                            if st.button("✅ Confirmar Exclusão", key=f"confirm_{product['id']}"):
                                try:
                                    supabase.table('products').delete().eq('id', product['id']).execute()

                                    if product['image_url']:
                                        file_path_image = product['image_url'].split('/')[-1].split('?')[0]
                                        file_path_qr = f"{product['id']}_qrcode.png"
                                        supabase.storage.from_(bucket_name).remove([file_path_image, file_path_qr])

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