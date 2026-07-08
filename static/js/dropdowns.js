document.addEventListener('DOMContentLoaded', function () {
    const schoolSelect = document.getElementById('id_school');
    const programSelect = document.getElementById('id_program');
    const branchSelect = document.getElementById('id_branch');

    // Helper to clear dropdowns
    function clearDropdown(selectElement, defaultText) {
        selectElement.innerHTML = `<option value="">${defaultText}</option>`;
        selectElement.disabled = true;
    }

    // Helper to populate dropdown
    function populateDropdown(selectElement, data, placeholder) {
        selectElement.innerHTML = `<option value="">${placeholder}</option>`;
        data.forEach(item => {
            const option = new Option(item.name, item.id);
            selectElement.add(option);
        });
        selectElement.disabled = false;
    }

    if (schoolSelect && programSelect && branchSelect) {
        // Initially disable dependent dropdowns
        programSelect.disabled = true;
        branchSelect.disabled = true;

        schoolSelect.addEventListener('change', function () {
            const schoolId = this.value;

            // Clear and disable children
            clearDropdown(programSelect, 'Select Program');
            clearDropdown(branchSelect, 'Select Branch');

            if (schoolId) {
                // Fetch programs
                fetch(`/admin/api/get-programs/?school_id=${schoolId}`)
                    .then(response => {
                        if (!response.ok) throw new Error('Network response was not ok');
                        return response.json();
                    })
                    .then(data => {
                        populateDropdown(programSelect, data.programs, 'Select Program');
                    })
                    .catch(error => console.error('Error fetching programs:', error));
            }
        });

        programSelect.addEventListener('change', function () {
            const programId = this.value;

            // Clear child
            clearDropdown(branchSelect, 'Select Branch');

            if (programId) {
                // Fetch branches
                fetch(`/admin/api/get-branches/?program_id=${programId}`)
                    .then(response => {
                        if (!response.ok) throw new Error('Network response was not ok');
                        return response.json();
                    })
                    .then(data => {
                        populateDropdown(branchSelect, data.branches, 'Select Branch');
                    })
                    .catch(error => console.error('Error fetching branches:', error));
            }
        });
    }
});
