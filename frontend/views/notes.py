import requests
import streamlit as st

from common import BACKEND_URL

st.title("📝 지식 노트")

with st.expander("새 노트 작성"):
    with st.form("create_note_form", clear_on_submit=True):
        title = st.text_input("제목")
        text = st.text_area("본문", height=150)
        create_submitted = st.form_submit_button("저장")

    if create_submitted:
        if not text:
            st.warning("본문을 입력해주세요.")
        else:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/notes",
                    json={"title": title, "text": text},
                    timeout=10,
                )
                resp.raise_for_status()
                st.success(f"저장됨 — note_id={resp.json()['note_id']}")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"저장 실패: {e}")

st.divider()

try:
    resp = requests.get(f"{BACKEND_URL}/notes", timeout=10)
    resp.raise_for_status()
    note_list = resp.json()["notes"]
except requests.RequestException as e:
    st.error(f"노트 조회 실패: {e}")
    note_list = []

if not note_list:
    st.caption("작성된 노트가 없습니다.")

for note in note_list:
    note_id = note["id"]

    with st.container(border=True):
        st.subheader(note["title"] or "(제목 없음)")
        st.caption(note["text"][:200] + ("..." if len(note["text"]) > 200 else ""))

        with st.expander("수정"):
            with st.form(f"edit_note_form_{note_id}"):
                edit_title = st.text_input("제목", value=note.get("title", ""))
                edit_text = st.text_area("본문", value=note.get("text", ""), height=150)
                edit_submitted = st.form_submit_button("저장")

            if edit_submitted:
                if not edit_text:
                    st.warning("본문을 입력해주세요.")
                else:
                    try:
                        edit_resp = requests.post(
                            f"{BACKEND_URL}/notes",
                            json={"title": edit_title, "text": edit_text, "update_existing_id": note_id},
                            timeout=10,
                        )
                        edit_resp.raise_for_status()
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"수정 실패: {e}")

        if st.button("삭제", key=f"delete_{note_id}"):
            try:
                delete_resp = requests.delete(f"{BACKEND_URL}/notes/{note_id}", timeout=10)
                delete_resp.raise_for_status()
                st.rerun()
            except requests.RequestException as e:
                st.error(f"삭제 실패: {e}")
