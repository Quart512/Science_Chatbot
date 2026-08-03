import requests
import streamlit as st

from common import BACKEND_URL

st.title("🧪 실험도구")

with st.expander("새 실험도구 등록"):
    with st.form("create_equipment_form", clear_on_submit=True):
        name = st.text_input("이름")
        purpose = st.text_input("목적")
        detail = st.text_area("세부내용", height=80)
        precautions = st.text_area("주의사항", height=80)
        create_submitted = st.form_submit_button("등록")

    if create_submitted:
        if not name:
            st.warning("이름을 입력해주세요.")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/equipment",
                    json={"name": name, "purpose": purpose, "detail": detail, "precautions": precautions},
                    timeout=10,
                )
                resp.raise_for_status()
                st.success(f"등록됨 — equipment_id={resp.json()['equipment_id']}")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"등록 실패: {e}")

st.divider()

try:
    resp = requests.get(f"{BACKEND_URL}/equipment", timeout=10)
    resp.raise_for_status()
    equipment_list = resp.json()["equipment"]
except requests.RequestException as e:
    st.error(f"실험도구 조회 실패: {e}")
    equipment_list = []

if not equipment_list:
    st.caption("등록된 실험도구가 없습니다.")

for item in equipment_list:
    item_id = item["id"]

    with st.container(border=True):
        st.subheader(item["name"])
        if item.get("purpose"):
            st.caption(f"목적: {item['purpose']}")
        if item.get("precautions"):
            st.warning(f"⚠️ {item['precautions']}")

        with st.expander("수정"):
            with st.form(f"edit_equipment_form_{item_id}"):
                edit_name = st.text_input("이름", value=item["name"])
                edit_purpose = st.text_input("목적", value=item.get("purpose", ""))
                edit_detail = st.text_area("세부내용", value=item.get("detail", ""), height=80)
                edit_precautions = st.text_area("주의사항", value=item.get("precautions", ""), height=80)
                edit_submitted = st.form_submit_button("저장")

            if edit_submitted:
                if not edit_name:
                    st.warning("이름을 입력해주세요.")
                else:
                    try:
                        edit_resp = requests.post(
                            f"{BACKEND_URL}/equipment",
                            json={
                                "name": edit_name, "purpose": edit_purpose,
                                "detail": edit_detail, "precautions": edit_precautions,
                                "update_existing_id": item_id,
                            },
                            timeout=10,
                        )
                        edit_resp.raise_for_status()
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"수정 실패: {e}")

        if st.button("삭제", key=f"delete_{item_id}"):
            try:
                delete_resp = requests.delete(f"{BACKEND_URL}/equipment/{item_id}", timeout=10)
                delete_resp.raise_for_status()
                st.rerun()
            except requests.RequestException as e:
                st.error(f"삭제 실패: {e}")
