use std::{
    sync::mpsc::{self, Receiver, Sender},
    thread,
};

use crate::{
    adapter::load_issue_detail_from_adapter,
    app::{DetailRequest, DetailResult},
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
