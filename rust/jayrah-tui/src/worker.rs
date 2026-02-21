use std::{
    sync::mpsc::{self, Receiver, Sender},
    thread,
};

use crate::{
    adapter::{
        add_issue_comment_from_adapter, apply_issue_transition_from_adapter,
        load_issue_comments_from_adapter, load_issue_detail_from_adapter,
        load_issue_transitions_from_adapter, update_custom_field_from_adapter,
        update_issue_components_from_adapter, update_issue_description_from_adapter,
        update_issue_labels_from_adapter, update_issue_summary_from_adapter,
    },
    app::{
        AddCommentRequest, AddCommentResult, ApplyTransitionRequest, ApplyTransitionResult,
        CommentRequest, CommentResult, DetailRequest, DetailResult, EditField, EditIssueRequest,
        EditIssueResult, TransitionRequest, TransitionResult,
    },
};

pub fn start_detail_worker() -> (Sender<DetailRequest>, Receiver<DetailResult>) {
    let (request_tx, request_rx) = mpsc::channel::<DetailRequest>();
    let (result_tx, result_rx) = mpsc::channel::<DetailResult>();

    thread::spawn(move || {
        while let Ok(mut request) = request_rx.recv() {
            // Coalesce a burst of selection changes and fetch only the latest key.
            while let Ok(newer_request) = request_rx.try_recv() {
                request = newer_request;
            }

            let result =
                load_issue_detail_from_adapter(&request.key).map_err(|error| error.to_string());

            if result_tx
                .send(DetailResult {
                    key: request.key,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

pub fn start_comment_worker() -> (Sender<CommentRequest>, Receiver<CommentResult>) {
    let (request_tx, request_rx) = mpsc::channel::<CommentRequest>();
    let (result_tx, result_rx) = mpsc::channel::<CommentResult>();

    thread::spawn(move || {
        while let Ok(mut request) = request_rx.recv() {
            // Coalesce rapid selection changes and fetch only the latest key.
            while let Ok(newer_request) = request_rx.try_recv() {
                request = newer_request;
            }

            let result =
                load_issue_comments_from_adapter(&request.key).map_err(|error| error.to_string());

            if result_tx
                .send(CommentResult {
                    key: request.key,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

pub fn start_add_comment_worker() -> (Sender<AddCommentRequest>, Receiver<AddCommentResult>) {
    let (request_tx, request_rx) = mpsc::channel::<AddCommentRequest>();
    let (result_tx, result_rx) = mpsc::channel::<AddCommentResult>();

    thread::spawn(move || {
        while let Ok(request) = request_rx.recv() {
            let result = add_issue_comment_from_adapter(&request.key, &request.body)
                .map_err(|error| error.to_string());

            if result_tx
                .send(AddCommentResult {
                    key: request.key,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

pub fn start_transition_worker() -> (Sender<TransitionRequest>, Receiver<TransitionResult>) {
    let (request_tx, request_rx) = mpsc::channel::<TransitionRequest>();
    let (result_tx, result_rx) = mpsc::channel::<TransitionResult>();

    thread::spawn(move || {
        while let Ok(mut request) = request_rx.recv() {
            // Coalesce rapid selection changes and fetch only the latest key.
            while let Ok(newer_request) = request_rx.try_recv() {
                request = newer_request;
            }

            let result = load_issue_transitions_from_adapter(&request.key)
                .map_err(|error| error.to_string());

            if result_tx
                .send(TransitionResult {
                    key: request.key,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

pub fn start_apply_transition_worker() -> (
    Sender<ApplyTransitionRequest>,
    Receiver<ApplyTransitionResult>,
) {
    let (request_tx, request_rx) = mpsc::channel::<ApplyTransitionRequest>();
    let (result_tx, result_rx) = mpsc::channel::<ApplyTransitionResult>();

    thread::spawn(move || {
        while let Ok(request) = request_rx.recv() {
            let result = apply_issue_transition_from_adapter(&request.key, &request.transition_id)
                .map_err(|error| error.to_string());

            if result_tx
                .send(ApplyTransitionResult {
                    key: request.key,
                    transition_name: request.transition_name,
                    to_status: request.to_status,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

pub fn start_edit_issue_worker() -> (Sender<EditIssueRequest>, Receiver<EditIssueResult>) {
    let (request_tx, request_rx) = mpsc::channel::<EditIssueRequest>();
    let (result_tx, result_rx) = mpsc::channel::<EditIssueResult>();

    thread::spawn(move || {
        while let Ok(request) = request_rx.recv() {
            let result = match request.field {
                EditField::Summary => {
                    update_issue_summary_from_adapter(&request.key, &request.value)
                        .map_err(|error| error.to_string())
                }
                EditField::Description => {
                    update_issue_description_from_adapter(&request.key, &request.value)
                        .map_err(|error| error.to_string())
                }
                EditField::Labels => {
                    update_issue_labels_from_adapter(&request.key, &csv_to_values(&request.value))
                        .map_err(|error| error.to_string())
                }
                EditField::Components => update_issue_components_from_adapter(
                    &request.key,
                    &csv_to_values(&request.value),
                )
                .map_err(|error| error.to_string()),
                EditField::CustomField => match request.custom_field.as_ref() {
                    Some(field) => {
                        update_custom_field_from_adapter(&request.key, field, &request.value)
                            .map_err(|error| error.to_string())
                    }
                    None => Err("custom field metadata is missing".to_string()),
                },
            };

            if result_tx
                .send(EditIssueResult {
                    key: request.key,
                    field: request.field,
                    value: request.value,
                    custom_field: request.custom_field,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

fn csv_to_values(value: &str) -> Vec<String> {
    value
        .split(',')
        .map(|entry| entry.trim())
        .filter(|entry| !entry.is_empty())
        .map(|entry| entry.to_string())
        .collect()
}
