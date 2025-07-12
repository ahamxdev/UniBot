def is_done(status_code: str, operation: str) -> bool:
    """
    Determine whether the current operation has completed successfully
    and no further requests are necessary.

    This function helps decide if the bot should stop sending requests
    based on the response status and the type of operation.

    Args:
        status_code (str): The status code from the response analysis.  
            Examples: "registered", "deleted", "not_found", etc.
        operation (str): The operation type being performed.  
            Valid values: "register" or "delete".

    Returns:
        bool:  
            - True if the operation is complete (no more requests needed).  
            - False if further attempts should continue.
    """
    if operation == "register":
        # If the course has been fully registered, stop retrying
        if status_code in ["registered", "already_registered", "conflict", "unit_limit_exceeded"]:
            return True
        # Otherwise keep trying (e.g., if course is not fully registered yet)
        return False

    if operation == "delete":
        # If course was successfully deleted or not found, stop retrying
        if status_code in ["deleted", "not_found", "unknown_delete"]:
            return True
        # Otherwise keep trying
        return False

    # Unknown operations: default to continue trying
    return False
