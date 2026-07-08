document.addEventListener('DOMContentLoaded', function () {
    // Modals
    const createFacultyBtn = document.getElementById('btn-create-faculty');
    const createSubjectBtn = document.getElementById('btn-create-subject');
    const modalFaculty = document.getElementById('modal-faculty');
    const modalSubject = document.getElementById('modal-subject');
    const closeBtns = document.querySelectorAll('.close-modal');

    function openModal(modal) {
        modal.classList.add('active');
    }

    if (createFacultyBtn) {
        createFacultyBtn.addEventListener('click', () => openModal(modalFaculty));
    }

    if (createSubjectBtn) {
        createSubjectBtn.addEventListener('click', () => openModal(modalSubject));
    }

    closeBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            this.closest('.modal').classList.remove('active');
        });
    });

    window.addEventListener('click', function (e) {
        if (e.target.classList.contains('modal')) {
            e.target.classList.remove('active');
        }
    });
});

