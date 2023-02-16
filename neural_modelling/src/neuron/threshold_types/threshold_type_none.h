/*
 * Copyright (c) 2017 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

//! \file
//! \brief Threshold that never fires
#ifndef _THRESHOLD_TYPE_NONE_H_
#define _THRESHOLD_TYPE_NONE_H_

#include "threshold_type.h"

struct threshold_type_params_t {
};

struct threshold_type_t {
};

static void threshold_type_initialise(UNUSED threshold_type_t *state,
		UNUSED threshold_type_params_t *params, UNUSED uint32_t n_steps_per_timestep) {
}

static void threshold_type_save_state(UNUSED threshold_type_t *state,
		UNUSED threshold_type_params_t *params) {
}

//! \brief Determines if the value given is above the threshold value
//! \param[in] value: The value to determine if it is above the threshold
//! \param[in] threshold_type: The parameters to use to determine the result
//! \return True if the neuron should fire
static inline bool threshold_type_is_above_threshold(
        UNUSED state_t value, UNUSED threshold_type_t *threshold_type) {
    return 0;
}

#endif // _THRESHOLD_TYPE_NONE_H_
