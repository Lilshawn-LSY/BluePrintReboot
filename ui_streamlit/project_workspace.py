from __future__ import annotations

from typing import Any

import streamlit as st

from storage.index_store import load_index
from storage.note_block_store import get_note_block
from storage.project_link_store import (
    ALLOWED_LINK_TYPES,
    create_project_link,
    delete_links_for_project,
    delete_project_link,
    list_links_for_project,
    list_links_for_target,
)
from storage.project_store import (
    ALLOWED_PROJECT_PRIORITIES,
    ALLOWED_PROJECT_STATUSES,
    create_project,
    delete_project,
    list_projects,
    update_project,
)


PROJECT_SELECTION_KEY = "project_workspace_selected_id"
PENDING_PROJECT_SELECTION_CLEAR_KEY = "pending_project_workspace_selection_clear"


def render_project_workspace() -> None:
    st.title("Project Workspace")
    st.caption("Projects collect links to papers and structured note blocks.")
    if st.session_state.pop(PENDING_PROJECT_SELECTION_CLEAR_KEY, False):
        st.session_state.pop(PROJECT_SELECTION_KEY, None)
    projects = list_projects()
    _render_create_project_form()
    if not projects:
        st.info("No projects yet. Create one to begin linking research material.")
        return

    labels = {project["id"]: _project_label(project) for project in projects}
    selected_id = st.selectbox(
        "Select project",
        list(labels),
        format_func=lambda project_id: labels.get(project_id, project_id),
        key=PROJECT_SELECTION_KEY,
    )
    project = next(project for project in projects if project["id"] == selected_id)
    _render_project_detail(project)


def render_paper_project_links(record: dict[str, str]) -> None:
    paper_id = str(record["paper_id"])
    projects = list_projects()
    project_by_id = {project["id"]: project for project in projects}
    links = list_links_for_target("paper", paper_id)

    if links:
        st.caption("Linked projects")
        for link in links:
            project = project_by_id.get(link["project_id"])
            project_name = project["name"] if project else link["project_id"]
            st.write(f"{project_name} - {_display_choice(link['link_type'])}")
            if link["note"]:
                st.caption(link["note"])
            if st.button("Unlink", key=f"unlink_paper_project_{link['id']}"):
                delete_project_link(link["id"])
                st.rerun()
    else:
        st.caption("This paper is not linked to a project.")

    if not projects:
        st.info("Create a project in Project Workspace before linking this paper.")
        return

    with st.form(key=f"link_paper_to_project_{paper_id}"):
        project_id = st.selectbox(
            "Project",
            [project["id"] for project in projects],
            format_func=lambda value: project_by_id[value]["name"],
        )
        link_type = st.selectbox("Link type", ALLOWED_LINK_TYPES)
        note = st.text_input("Link note")
        submitted = st.form_submit_button("Link paper")
    if submitted:
        create_project_link(
            project_id=project_id,
            target_type="paper",
            target_id=paper_id,
            paper_id=paper_id,
            link_type=link_type,
            note=note,
        )
        st.rerun()


def render_note_block_project_links(record: dict[str, str], block: dict[str, Any]) -> None:
    paper_id = str(record["paper_id"])
    block_id = str(block["id"])
    projects = list_projects()
    project_by_id = {project["id"]: project for project in projects}
    links = list_links_for_target("note_block", block_id)

    if links:
        linked_labels = [
            f"{project_by_id.get(link['project_id'], {}).get('name', link['project_id'])} "
            f"({_display_choice(link['link_type'])})"
            for link in links
        ]
        st.caption("Linked projects: " + ", ".join(linked_labels))
        for link in links:
            project_name = project_by_id.get(link["project_id"], {}).get("name", link["project_id"])
            if st.button(
                f"Unlink from {project_name}",
                key=f"unlink_note_block_project_{block_id}_{link['id']}",
            ):
                delete_project_link(link["id"])
                st.rerun()

    if not projects:
        return

    with st.expander("Link to Project"):
        project_id = st.selectbox(
            "Project",
            [project["id"] for project in projects],
            format_func=lambda value: project_by_id[value]["name"],
            key=f"note_block_project_{block_id}",
        )
        link_type = st.selectbox(
            "Link type",
            ALLOWED_LINK_TYPES,
            key=f"note_block_link_type_{block_id}",
        )
        note = st.text_input("Link note", key=f"note_block_link_note_{block_id}")
        if st.button("Create project link", key=f"create_note_block_project_link_{block_id}"):
            create_project_link(
                project_id=project_id,
                target_type="note_block",
                target_id=block_id,
                paper_id=paper_id,
                link_type=link_type,
                note=note,
            )
            st.rerun()


def _render_create_project_form() -> None:
    with st.expander("Create project"):
        with st.form("create_project_form"):
            name = st.text_input("Project name")
            description = st.text_area("Description", height=100)
            status = st.selectbox("Status", ALLOWED_PROJECT_STATUSES)
            priority = st.selectbox(
                "Priority",
                ALLOWED_PROJECT_PRIORITIES,
                index=ALLOWED_PROJECT_PRIORITIES.index("normal"),
            )
            tags = st.text_input("Tags (comma-separated)")
            submitted = st.form_submit_button("Create project")
    if submitted:
        try:
            project = create_project(name, description, status, priority, tags)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state[PROJECT_SELECTION_KEY] = project["id"]
            st.rerun()


def _render_project_detail(project: dict[str, Any]) -> None:
    st.subheader(project["name"])
    st.caption(
        f"Status: {_display_choice(project['status'])} | "
        f"Priority: {_display_choice(project['priority'])} | Updated: {project['updated_at']}"
    )
    if project["description"]:
        st.write(project["description"])
    if project["tags"]:
        st.caption("Tags: " + ", ".join(project["tags"]))

    with st.expander("Edit project"):
        with st.form(key=f"edit_project_{project['id']}"):
            name = st.text_input("Project name", value=project["name"])
            description = st.text_area("Description", value=project["description"], height=100)
            status = st.selectbox(
                "Status",
                ALLOWED_PROJECT_STATUSES,
                index=ALLOWED_PROJECT_STATUSES.index(project["status"]),
            )
            priority = st.selectbox(
                "Priority",
                ALLOWED_PROJECT_PRIORITIES,
                index=ALLOWED_PROJECT_PRIORITIES.index(project["priority"]),
            )
            tags = st.text_input("Tags (comma-separated)", value=", ".join(project["tags"]))
            submitted = st.form_submit_button("Save project")
        if submitted:
            try:
                update_project(
                    project["id"],
                    {
                        "name": name,
                        "description": description,
                        "status": status,
                        "priority": priority,
                        "tags": tags,
                    },
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()

    if st.button("Delete project and its links", key=f"delete_project_{project['id']}"):
        delete_links_for_project(project["id"])
        delete_project(project["id"])
        st.session_state[PENDING_PROJECT_SELECTION_CLEAR_KEY] = True
        st.rerun()

    links = list_links_for_project(project["id"])
    paper_links = [link for link in links if link["target_type"] == "paper"]
    block_links = [link for link in links if link["target_type"] == "note_block"]
    paper_by_id = _paper_lookup()

    st.write("Linked Papers")
    if not paper_links:
        st.info("No papers linked to this project.")
    for link in paper_links:
        _render_linked_paper(link, paper_by_id)

    st.write("Linked Structured Note Blocks")
    if not block_links:
        st.info("No structured note blocks linked to this project.")
    for link in block_links:
        _render_linked_note_block(link, paper_by_id)


def _render_linked_paper(link: dict[str, Any], paper_by_id: dict[str, dict[str, str]]) -> None:
    record = paper_by_id.get(link["target_id"], {})
    title = record.get("title") or record.get("filename") or link["target_id"]
    filename = record.get("filename", "")
    with st.container(border=True):
        st.write(title)
        st.caption(" | ".join(value for value in (filename, _display_choice(link["link_type"])) if value))
        if link["note"]:
            st.write(link["note"])
        if st.button("Unlink paper", key=f"project_workspace_unlink_{link['id']}"):
            delete_project_link(link["id"])
            st.rerun()


def _render_linked_note_block(link: dict[str, Any], paper_by_id: dict[str, dict[str, str]]) -> None:
    block = get_note_block(link["paper_id"], link["target_id"]) if link["paper_id"] else None
    paper = paper_by_id.get(link["paper_id"], {})
    paper_title = paper.get("title") or paper.get("filename") or link["paper_id"] or "paper unknown"
    with st.container(border=True):
        if block:
            title = block["title"] or block["block_type"].replace("_", " ").title()
            st.write(f"{title} - {_display_choice(block['block_type'])}")
            details = [
                value
                for value in (
                    f"Paper: {paper_title}",
                    f"Page: {block['page']}" if block["page"] else "",
                    f"Figure: {block['figure']}" if block["figure"] else "",
                    f"Tags: {', '.join(block['tags'])}" if block["tags"] else "",
                    f"Link: {_display_choice(link['link_type'])}",
                )
                if value
            ]
            st.caption(" | ".join(details))
            if block["text"]:
                st.write(block["text"])
        else:
            st.write(f"Missing note block: {link['target_id']}")
            st.caption(f"Paper: {paper_title} | Link: {_display_choice(link['link_type'])}")
        if link["note"]:
            st.write(link["note"])
        if st.button("Unlink note block", key=f"project_workspace_unlink_{link['id']}"):
            delete_project_link(link["id"])
            st.rerun()


def _paper_lookup() -> dict[str, dict[str, str]]:
    return {
        str(record["paper_id"]): {key: str(value) for key, value in record.items()}
        for record in load_index().to_dict("records")
    }


def _project_label(project: dict[str, Any]) -> str:
    return f"{project['name']} ({_display_choice(project['status'])})"


def _display_choice(value: str) -> str:
    return str(value).replace("_", " ").title()
